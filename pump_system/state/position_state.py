from __future__ import annotations

import logging
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

    async def refresh(self) -> None:
        """Refresh current positions and open orders from Binance."""
        if not self.exchange_client.has_private_api:
            self.logger.warning("[ASSUMPTION] private API unavailable; position sync skipped.")
            self.positions = {}
            self.open_order_counts = {}
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
            for symbol in set(counts).union(positions):
                algo_orders = await self.exchange_client.get_open_algo_orders(symbol=symbol, algo_type="CONDITIONAL")
                for order in algo_orders:
                    algo_symbol = order["symbol"]
                    counts[algo_symbol] = counts.get(algo_symbol, 0) + 1
            self.open_order_counts = counts

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
