import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from config import load_settings
from pump_system.execution.order_service import OrderService
from pump_system.models import Kline, SignalDecision


class DummyExchangeClient:
    has_private_api = False


class DummySymbolRegistry:
    def should_evaluate(self, symbol: str) -> bool:
        return symbol == "HOMEUSDT"

    def get(self, symbol: str):
        return SimpleNamespace(order_types=("MARKET", "STOP_MARKET"))


class DummyStagingStore:
    def __init__(self, current_bar: Kline) -> None:
        self.current_bar = current_bar

    async def get_signal_snapshot(self, symbol: str, signal_limit: int):
        return ([self.current_bar], self.current_bar)


class DummyPositionState:
    async def refresh_symbol(self, symbol: str) -> None:
        return None

    def has_open_position(self, symbol: str) -> bool:
        return False

    def active_position_count(self) -> int:
        return 0


class DummySignalEngine:
    def __init__(self, decision: SignalDecision) -> None:
        self.decision = decision

    def evaluate(self, symbol: str, finalized_bars, current_bar) -> SignalDecision:
        return self.decision


class DummyNotifier:
    def __init__(self) -> None:
        self.info_events = []
        self.error_events = []

    async def send_info(self, event_type, **kwargs):
        self.info_events.append((event_type, kwargs))

    async def send_error(self, event_type, **kwargs):
        self.error_events.append((event_type, kwargs))


class DummySignalAuditWriter:
    def __init__(self) -> None:
        self.signal_decisions = []
        self.order_gates = []

    def record_signal_decision(self, **kwargs):
        self.signal_decisions.append(kwargs)

    def record_order_gate(self, **kwargs):
        self.order_gates.append(kwargs)


def test_signal_notification_includes_bar_key_for_dedupe() -> None:
    settings = load_settings()
    open_time = datetime(2026, 5, 7, 1, 15, tzinfo=timezone.utc)
    current_bar = Kline(
        symbol="HOMEUSDT",
        interval=settings.strategy.interval,
        open_time=open_time,
        close_time=open_time + timedelta(minutes=15),
        open_price=Decimal("0.014"),
        high_price=Decimal("0.0142"),
        low_price=Decimal("0.0135"),
        close_price=Decimal("0.0141"),
        volume=Decimal("1000000"),
        closed=False,
        event_time=open_time,
    )
    decision = SignalDecision(
        symbol="HOMEUSDT",
        triggered=True,
        reason="test",
        metrics={"mode": "15m_only"},
        stop_reference_low=Decimal("0.0135"),
        current_price=Decimal("0.0141"),
    )
    notifier = DummyNotifier()
    service = OrderService(
        settings=settings,
        exchange_client=DummyExchangeClient(),
        symbol_registry=DummySymbolRegistry(),
        staging_store=DummyStagingStore(current_bar),
        position_state=DummyPositionState(),
        signal_engine=DummySignalEngine(decision),
        fallback_manager=SimpleNamespace(),
        notifier=notifier,
    )

    asyncio.run(service.on_market_update("HOMEUSDT"))

    assert notifier.info_events[0][0] == "SIGNAL_TRIGGERED"
    assert notifier.info_events[0][1]["details"]["bar_key"] == open_time.isoformat()


def test_signal_audit_records_non_triggered_decision() -> None:
    settings = load_settings()
    open_time = datetime(2026, 5, 7, 1, 15, tzinfo=timezone.utc)
    current_bar = Kline(
        symbol="HOMEUSDT",
        interval=settings.strategy.interval,
        open_time=open_time,
        close_time=open_time + timedelta(minutes=15),
        open_price=Decimal("0.014"),
        high_price=Decimal("0.0142"),
        low_price=Decimal("0.0135"),
        close_price=Decimal("0.0141"),
        volume=Decimal("1000000"),
        closed=False,
        event_time=open_time,
    )
    decision = SignalDecision(
        symbol="HOMEUSDT",
        triggered=False,
        reason="15m_volume_too_low",
        metrics={"mode": "15m_only"},
        stop_reference_low=current_bar.low_price,
        current_price=current_bar.close_price,
    )
    audit_writer = DummySignalAuditWriter()
    service = OrderService(
        settings=settings,
        exchange_client=DummyExchangeClient(),
        symbol_registry=DummySymbolRegistry(),
        staging_store=DummyStagingStore(current_bar),
        position_state=DummyPositionState(),
        signal_engine=DummySignalEngine(decision),
        fallback_manager=SimpleNamespace(),
        signal_audit_writer=audit_writer,
    )

    asyncio.run(service.on_market_update("HOMEUSDT"))

    assert len(audit_writer.signal_decisions) == 1
    assert audit_writer.signal_decisions[0]["symbol"] == "HOMEUSDT"
    assert audit_writer.signal_decisions[0]["decision"].triggered is False
    assert audit_writer.order_gates == []
