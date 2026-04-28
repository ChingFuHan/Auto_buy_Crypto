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
    delta = int(interval[:-1]) if interval.endswith("m") else 1
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


def test_signal_triggers_from_3m_only_context(monkeypatch) -> None:
    monkeypatch.setenv("STRATEGY_INTERVAL", "3m")
    settings = load_settings()
    engine = SignalEngine(settings.strategy)

    finalized_3m = [
        make_bar(i * 3, "3m", "1.00", "1.004", "0.996", "1.00", "300")
        for i in range(20)
    ]
    current_3m = make_bar(60, "3m", "1.00", "1.06", "0.998", "1.05", "900", closed=False)

    decision = engine.evaluate("TESTUSDT", finalized_3m, current_3m)

    assert decision.triggered is True
    assert decision.stop_reference_low == Decimal("0.998")
    assert decision.metrics["mode"] == "3m_only"
    assert decision.metrics["stop_source"] == "in_progress_3m_low"


def test_signal_blocks_when_3m_context_is_missing(monkeypatch) -> None:
    monkeypatch.setenv("STRATEGY_INTERVAL", "3m")
    settings = load_settings()
    engine = SignalEngine(settings.strategy)

    finalized_3m = [
        make_bar(i * 3, "3m", "1.00", "1.004", "0.996", "1.00", "300")
        for i in range(20)
    ]

    decision = engine.evaluate("TESTUSDT", finalized_3m, None)

    assert decision.triggered is False
    assert decision.reason == "missing_in_progress_3m"


def test_signal_labels_follow_15m_strategy_interval(monkeypatch) -> None:
    monkeypatch.setenv("STRATEGY_INTERVAL", "15m")
    settings = load_settings()
    engine = SignalEngine(settings.strategy)

    finalized_15m = [
        make_bar(i * 15, "15m", "1.00", "1.004", "0.996", "1.00", "300")
        for i in range(20)
    ]
    current_15m = make_bar(300, "15m", "1.00", "1.06", "0.998", "1.05", "900", closed=False)

    decision = engine.evaluate("TESTUSDT", finalized_15m, current_15m)

    assert decision.triggered is True
    assert decision.metrics["mode"] == "15m_only"
    assert decision.metrics["stop_source"] == "in_progress_15m_low"
    assert decision.metrics["breakout_15m"] == "True"


def test_signal_blocks_when_15m_context_is_missing(monkeypatch) -> None:
    monkeypatch.setenv("STRATEGY_INTERVAL", "15m")
    settings = load_settings()
    engine = SignalEngine(settings.strategy)

    finalized_15m = [
        make_bar(i * 15, "15m", "1.00", "1.004", "0.996", "1.00", "300")
        for i in range(20)
    ]

    decision = engine.evaluate("TESTUSDT", finalized_15m, None)

    assert decision.triggered is False
    assert decision.reason == "missing_in_progress_15m"


def test_settings_15m_strategy_interval_targets_15m_runtime_files(monkeypatch) -> None:
    monkeypatch.setenv("STRATEGY_INTERVAL", "15m")

    settings = load_settings()

    assert settings.strategy_interval == "15m"
    assert settings.strategy_table_name == "public.semi_auto_price_future_15m"
    assert settings.strategy_staging_csv_path.name == "inprogress_15m.csv"
    assert settings.strategy_interval_ms == 900_000


def test_settings_default_strategy_interval_is_15m(monkeypatch) -> None:
    monkeypatch.delenv("STRATEGY_INTERVAL", raising=False)

    settings = load_settings()

    assert settings.strategy_interval == "15m"
    assert settings.strategy_table_name == "public.semi_auto_price_future_15m"


def test_settings_15m_uses_signal_15m_thresholds_not_3m(monkeypatch) -> None:
    monkeypatch.setenv("STRATEGY_INTERVAL", "15m")
    monkeypatch.setenv("SIGNAL_3M_LOOKBACK", "99")
    monkeypatch.setenv("SIGNAL_3M_RETURN_PCT_MIN", "0.99")
    monkeypatch.setenv("SIGNAL_15M_LOOKBACK", "7")
    monkeypatch.setenv("SIGNAL_15M_RETURN_PCT_MIN", "0.025")

    settings = load_settings()

    assert settings.strategy.lookback == 7
    assert settings.strategy.return_pct_min == Decimal("0.025")


def test_settings_3m_uses_signal_3m_thresholds_not_15m(monkeypatch) -> None:
    monkeypatch.setenv("STRATEGY_INTERVAL", "3m")
    monkeypatch.setenv("SIGNAL_15M_LOOKBACK", "99")
    monkeypatch.setenv("SIGNAL_15M_RETURN_PCT_MIN", "0.99")
    monkeypatch.setenv("SIGNAL_3M_LOOKBACK", "8")
    monkeypatch.setenv("SIGNAL_3M_RETURN_PCT_MIN", "0.018")

    settings = load_settings()

    assert settings.strategy.lookback == 8
    assert settings.strategy.return_pct_min == Decimal("0.018")
