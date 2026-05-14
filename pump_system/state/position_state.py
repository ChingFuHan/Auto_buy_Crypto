from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal

from pump_system.models import PositionSnapshot


class PositionState:
    """In-memory view of current futures positions and open order counts."""

    def __init__(self, exchange_client, enable_open_order_sync: bool = True) -> None:
        self.exchange_client = exchange_client
        self.enable_open_order_sync = enable_open_order_sync
        self.logger = logging.getLogger("state.position")
        self.positions: dict[str, PositionSnapshot] = {}
        self.open_order_counts: dict[str, int] = {}
        self.open_algo_orders: dict[str, list[dict]] = {}
        self.last_refresh_monotonic: float = 0.0
        self._refresh_lock = asyncio.Lock()

    async def refresh(self) -> None:
        """Refresh current positions and open orders from Binance."""
        async with self._refresh_lock:
            await self._refresh_from_exchange()

    async def ensure_fresh(self, max_age_seconds: float) -> None:
        """Refresh the shared account snapshot only when it is stale."""
        if not self.exchange_client.has_private_api:
            return

        now = time.monotonic()
        if self.last_refresh_monotonic and now - self.last_refresh_monotonic < max_age_seconds:
            return

        async with self._refresh_lock:
            now = time.monotonic()
            if self.last_refresh_monotonic and now - self.last_refresh_monotonic < max_age_seconds:
                return
            await self._refresh_from_exchange()

    async def _refresh_from_exchange(self) -> None:
        if not self.exchange_client.has_private_api:
            self.logger.warning("[ASSUMPTION] private API unavailable; position sync skipped.")
            self.positions = {}
            self.open_order_counts = {}
            self.open_algo_orders = {}
            self.last_refresh_monotonic = time.monotonic()
            return

        payload = await self.exchange_client.get_position_risk()
        positions: dict[str, PositionSnapshot] = {}
        for item in payload:
            quantity = Decimal(str(item.get("positionAmt", "0")))
            if quantity <= Decimal("0"):
                continue
            positions[item["symbol"]] = PositionSnapshot(
                symbol=item["symbol"],
                quantity=quantity.copy_abs(),
                entry_price=Decimal(str(item.get("entryPrice", "0"))),
                leverage=int(str(item.get("leverage", "1"))),
                margin_type=str(item.get("marginType", "cross")).lower(),
                unrealized_pnl=Decimal(str(item.get("unRealizedProfit", item.get("unrealizedProfit", "0")))),
            )
        self.positions = positions

        if self.enable_open_order_sync:
            open_orders = await self.exchange_client.get_open_orders()
            counts: dict[str, int] = {}
            for order in open_orders:
                symbol = order["symbol"]
                counts[symbol] = counts.get(symbol, 0) + 1
            open_algo_orders: dict[str, list[dict]] = {}
            for symbol in set(counts).union(positions):
                algo_orders = await self.exchange_client.get_open_algo_orders(symbol=symbol, algo_type="CONDITIONAL")
                open_algo_orders[symbol] = list(algo_orders)
                for order in algo_orders:
                    algo_symbol = order["symbol"]
                    counts[algo_symbol] = counts.get(algo_symbol, 0) + 1
            self.open_order_counts = counts
            self.open_algo_orders = open_algo_orders
        else:
            self.open_order_counts = {}
            self.open_algo_orders = {}
        self.last_refresh_monotonic = time.monotonic()

    async def refresh_symbol(self, symbol: str) -> None:
        """Refresh a single symbol position by refetching only that symbol's risk."""
        if not self.exchange_client.has_private_api:
            self.positions.pop(symbol, None)
            return

        try:
            payload = await self.exchange_client.get_position_risk(symbol=symbol)
        except Exception as exc:
            self.logger.warning("refresh_symbol failed symbol=%s error=%s; falling back to full refresh", symbol, exc)
            await self.refresh()
            return

        found = False
        for item in payload:
            if item.get("symbol") != symbol:
                continue
            quantity = Decimal(str(item.get("positionAmt", "0")))
            if quantity <= Decimal("0"):
                continue
            self.positions[symbol] = PositionSnapshot(
                symbol=symbol,
                quantity=quantity.copy_abs(),
                entry_price=Decimal(str(item.get("entryPrice", "0"))),
                leverage=int(str(item.get("leverage", "1"))),
                margin_type=str(item.get("marginType", "cross")).lower(),
                unrealized_pnl=Decimal(str(item.get("unRealizedProfit", item.get("unrealizedProfit", "0")))),
            )
            found = True
            break
        if not found:
            self.positions.pop(symbol, None)

    def has_open_position(self, symbol: str) -> bool:
        snapshot = self.positions.get(symbol)
        return snapshot is not None and snapshot.has_position

    def active_position_count(self) -> int:
        return sum(1 for snapshot in self.positions.values() if snapshot.has_position)

    def get_quantity(self, symbol: str) -> Decimal:
        snapshot = self.positions.get(symbol)
        return Decimal("0") if snapshot is None else snapshot.quantity

    def get_open_algo_orders(self, symbol: str) -> list[dict]:
        return list(self.open_algo_orders.get(symbol, []))

    def upsert_position(self, snapshot: PositionSnapshot) -> None:
        self.positions[snapshot.symbol] = snapshot

    def upsert_open_algo_order(self, symbol: str, order: dict) -> None:
        client_algo_id = str(order.get("clientAlgoId", ""))
        existing = self.open_algo_orders.get(symbol, [])
        if client_algo_id:
            existing = [item for item in existing if str(item.get("clientAlgoId", "")) != client_algo_id]
        updated = [*existing, dict(order)]
        self.open_algo_orders[symbol] = updated
        self.open_order_counts[symbol] = max(self.open_order_counts.get(symbol, 0), len(updated))
