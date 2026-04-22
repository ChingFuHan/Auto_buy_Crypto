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
            self.open_order_counts = counts

    async def refresh_symbol(self, symbol: str) -> None:
        """Refresh a single symbol position by refetching position risk."""
        await self.refresh()
        if symbol not in self.positions:
            self.positions.pop(symbol, None)

    def has_open_position(self, symbol: str) -> bool:
        snapshot = self.positions.get(symbol)
        return snapshot is not None and snapshot.has_position

    def active_position_count(self) -> int:
        return sum(1 for snapshot in self.positions.values() if snapshot.has_position)

    def get_quantity(self, symbol: str) -> Decimal:
        snapshot = self.positions.get(symbol)
        return Decimal("0") if snapshot is None else snapshot.quantity
