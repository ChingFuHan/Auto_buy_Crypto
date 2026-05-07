import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx

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


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        telegram_configured=True,
        telegram_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="chat-id",
    )


class FakeTelegramClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = list(responses)
        self.requests: list[dict] = []

    async def post(self, path: str, json: dict) -> httpx.Response:
        self.requests.append({"path": path, "json": json})
        return self.responses.pop(0)

    async def aclose(self) -> None:
        return None


def test_duplicate_signal_is_dropped_when_bar_key_matches() -> None:
    notifier = TelegramNotifier(_settings())

    async def scenario() -> None:
        await notifier.send_info("SIGNAL_TRIGGERED", symbol="HOMEUSDT", details={"bar_key": "2026-05-07T01:15:00+00:00"})
        await notifier.send_info("SIGNAL_TRIGGERED", symbol="HOMEUSDT", details={"bar_key": "2026-05-07T01:15:00+00:00"})

    asyncio.run(scenario())

    assert notifier._queue.qsize() == 1


def test_deferred_high_priority_message_is_sent_after_flood_wait_without_new_queue_item() -> None:
    notifier = TelegramNotifier(_settings())
    fake_client = FakeTelegramClient(
        [
            httpx.Response(
                429,
                json={"ok": False, "error_code": 429, "description": "Too Many Requests", "parameters": {"retry_after": 1}},
                request=httpx.Request("POST", "https://api.telegram.org/bottoken/sendMessage"),
            ),
            httpx.Response(
                200,
                json={"ok": True, "result": {}},
                request=httpx.Request("POST", "https://api.telegram.org/bottoken/sendMessage"),
            ),
        ]
    )
    notifier._client = fake_client

    async def scenario() -> None:
        notifier._worker = asyncio.create_task(notifier._run())
        await notifier.send_error("ENTRY_ORDER_FAILED", symbol="HOMEUSDT", error_message="simulated")
        await asyncio.sleep(1.3)
        await notifier.close()

    asyncio.run(scenario())

    assert len(fake_client.requests) == 2
    assert fake_client.requests[0]["json"]["text"].startswith("[ERROR] ENTRY_ORDER_FAILED")
    assert fake_client.requests[1]["json"]["text"].startswith("[ERROR] ENTRY_ORDER_FAILED")
