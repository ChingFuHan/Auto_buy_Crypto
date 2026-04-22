from datetime import datetime, timedelta, timezone
from decimal import Decimal

from config import load_settings
from pump_system.models import Kline
from pump_system.strategy.signal_engine import SignalEngine


UTC = timezone.utc


def make_bar(
    minute: int,
    interval: str,
    open_price: str,
    high_price: str,
    low_price: str,
    close_price: str,
    volume: str,
    closed: bool = True,
) -> Kline:
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC) + timedelta(minutes=minute)
    delta = 1 if interval == "1m" else 3
    return Kline(
        symbol="TESTUSDT",
        interval=interval,
        open_time=start,
        close_time=start + timedelta(minutes=delta) - timedelta(milliseconds=1),
        open_price=Decimal(open_price),
        high_price=Decimal(high_price),
        low_price=Decimal(low_price),
        close_price=Decimal(close_price),
        volume=Decimal(volume),
        closed=closed,
        event_time=start,
    )


def test_signal_triggers_when_both_timeframes_align() -> None:
    settings = load_settings()
    engine = SignalEngine(settings.strategy)

    finalized_1m = [
        make_bar(i, "1m", "1.00", "1.002", "0.998", "1.00", "100")
        for i in range(20)
    ]
    finalized_3m = [
        make_bar(i * 3, "3m", "1.00", "1.004", "0.996", "1.00", "300")
        for i in range(20)
    ]
    current_1m = make_bar(20, "1m", "1.00", "1.05", "0.999", "1.04", "450", closed=False)
    current_3m = make_bar(60, "3m", "1.00", "1.06", "0.998", "1.05", "900", closed=False)

    decision = engine.evaluate("TESTUSDT", finalized_1m, current_1m, finalized_3m, current_3m)

    assert decision.triggered is True
    assert decision.stop_reference_low == Decimal("0.999")


def test_signal_blocks_when_3m_context_is_missing() -> None:
    settings = load_settings()
    engine = SignalEngine(settings.strategy)

    finalized_1m = [
        make_bar(i, "1m", "1.00", "1.01", "0.99", "1.00", "100")
        for i in range(20)
    ]
    current_1m = make_bar(20, "1m", "1.00", "1.05", "0.999", "1.04", "450", closed=False)

    decision = engine.evaluate("TESTUSDT", finalized_1m, current_1m, [], None)

    assert decision.triggered is False
    assert decision.reason == "missing_in_progress_bars"
