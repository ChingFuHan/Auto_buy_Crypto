from datetime import datetime, timezone

from pump_system.notify.telegram_notifier import TelegramNotifier


def test_build_message_contains_required_fields() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    message = TelegramNotifier.build_message(
        level="ERROR",
        event_type="STOP_ORDER_FAILED",
        timestamp=timestamp,
        symbol="BTCUSDT",
        side="SELL",
        quantity="0.01",
        entry_price="94500",
        stop_price="94000",
        working_type="CONTRACT_PRICE",
        order_id="12345",
        error_message="native_stop_failed_after_retries",
        details={"attempt": "3/3"},
    )

    assert "[ERROR] STOP_ORDER_FAILED" in message
    assert "timestamp: 2026-01-01T00:00:00+00:00" in message
    assert "symbol: BTCUSDT" in message
    assert "side: SELL" in message
    assert "quantity: 0.01" in message
    assert "entry_price: 94500" in message
    assert "stop_price: 94000" in message
    assert "workingType: CONTRACT_PRICE" in message
    assert "order_id: 12345" in message
    assert "error: native_stop_failed_after_retries" in message
    assert "attempt: 3/3" in message
