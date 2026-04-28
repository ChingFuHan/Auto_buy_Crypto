from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any


UTC = timezone.utc
UTC_PLUS_8 = timezone(timedelta(hours=8))


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(slots=True)
class Kline:
    symbol: str
    interval: str
    open_time: datetime
    close_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    closed: bool
    event_time: datetime | None = None

    @property
    def db_timestamp(self) -> datetime:
        return self.open_time.astimezone(UTC_PLUS_8).replace(tzinfo=None)

    @property
    def as_db_row(self) -> tuple[datetime, str, float, float, float, float, float]:
        return (
            self.db_timestamp,
            self.symbol,
            float(self.close_price),
            float(self.high_price),
            float(self.low_price),
            float(self.open_price),
            float(self.volume),
        )


@dataclass(slots=True)
class SymbolInfo:
    symbol: str
    status: str
    contract_type: str
    quote_asset: str
    margin_asset: str
    tick_size: Decimal
    min_qty: Decimal
    max_qty: Decimal
    step_size: Decimal
    market_min_qty: Decimal
    market_max_qty: Decimal
    market_step_size: Decimal
    min_notional: Decimal
    trigger_protect: Decimal
    order_types: tuple[str, ...]

    @classmethod
    def from_exchange_payload(cls, payload: dict[str, Any]) -> "SymbolInfo":
        filters = {item["filterType"]: item for item in payload.get("filters", [])}
        price_filter = filters.get("PRICE_FILTER", {})
        lot_size = filters.get("LOT_SIZE", {})
        market_lot_size = filters.get("MARKET_LOT_SIZE", lot_size)
        min_notional = filters.get("MIN_NOTIONAL", {})
        return cls(
            symbol=payload["symbol"],
            status=payload["status"],
            contract_type=payload["contractType"],
            quote_asset=payload["quoteAsset"],
            margin_asset=payload["marginAsset"],
            tick_size=Decimal(price_filter.get("tickSize", "0.00000001")),
            min_qty=Decimal(lot_size.get("minQty", "0")),
            max_qty=Decimal(lot_size.get("maxQty", "0")),
            step_size=Decimal(lot_size.get("stepSize", "0.00000001")),
            market_min_qty=Decimal(market_lot_size.get("minQty", lot_size.get("minQty", "0"))),
            market_max_qty=Decimal(market_lot_size.get("maxQty", lot_size.get("maxQty", "0"))),
            market_step_size=Decimal(market_lot_size.get("stepSize", lot_size.get("stepSize", "0.00000001"))),
            min_notional=Decimal(min_notional.get("notional", "0")),
            trigger_protect=Decimal(payload.get("triggerProtect", "0")),
            order_types=tuple(payload.get("orderTypes", [])),
        )


@dataclass(slots=True)
class SignalDecision:
    symbol: str
    triggered: bool
    reason: str
    metrics: dict[str, str] = field(default_factory=dict)
    stop_reference_low: Decimal | None = None
    current_price: Decimal | None = None


@dataclass(slots=True)
class PositionSnapshot:
    symbol: str
    quantity: Decimal
    entry_price: Decimal
    leverage: int
    margin_type: str
    unrealized_pnl: Decimal

    @property
    def has_position(self) -> bool:
        return self.quantity > Decimal("0")


@dataclass(slots=True)
class SizingDecision:
    symbol: str
    quantity: Decimal
    requested_notional: Decimal
    final_notional: Decimal
    available_balance: Decimal
    max_affordable_notional: Decimal
    leverage: int
    used_max_affordable: bool
    can_trade: bool
    reason: str


@dataclass(slots=True)
class FallbackStopRecord:
    symbol: str
    stop_price: Decimal
    quantity: Decimal
    working_type: str
    active: bool
    status: str
    entry_price: Decimal
    entry_order_id: str
    last_price: Decimal | None
    retry_count: int
    last_error: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "FallbackStopRecord":
        return cls(
            symbol=row["symbol"],
            stop_price=Decimal(row["stop_price"]),
            quantity=Decimal(row["quantity"]),
            working_type=row["working_type"],
            active=row["active"].lower() == "true",
            status=row["status"],
            entry_price=Decimal(row["entry_price"]),
            entry_order_id=row["entry_order_id"],
            last_price=Decimal(row["last_price"]) if row.get("last_price") else None,
            retry_count=int(row.get("retry_count", "0")),
            last_error=row.get("last_error", ""),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def to_row(self) -> dict[str, str]:
        return {
            "symbol": self.symbol,
            "stop_price": format(self.stop_price, "f"),
            "quantity": format(self.quantity, "f"),
            "working_type": self.working_type,
            "active": str(self.active),
            "status": self.status,
            "entry_price": format(self.entry_price, "f"),
            "entry_order_id": self.entry_order_id,
            "last_price": "" if self.last_price is None else format(self.last_price, "f"),
            "retry_count": str(self.retry_count),
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(slots=True)
class NativeStopTracker:
    symbol: str
    client_order_id: str
    algo_id: str
    stop_price: Decimal
    quantity: Decimal
    working_type: str
    entry_price: Decimal
    missing_reported: bool = False
