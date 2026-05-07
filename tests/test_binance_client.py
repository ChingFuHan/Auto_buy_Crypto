import asyncio
from types import SimpleNamespace

import httpx

from config import RetryConfig
from pump_system.exchange.binance_client import BinanceClient


class DummyNotifier:
    def __init__(self) -> None:
        self.warning_events = []
        self.error_events = []

    async def send_warning(self, event_type, **kwargs):
        self.warning_events.append((event_type, kwargs))

    async def send_error(self, event_type, **kwargs):
        self.error_events.append((event_type, kwargs))


class FakeHttpClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def request(self, method, path, params=None):
        self.calls.append((method, path, dict(params or {})))
        return self.responses.pop(0)

    async def aclose(self):
        return None


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        api_key="api-key",
        api_secret="api-secret",
        rest_base_url="https://example.test",
        retry=RetryConfig(max_attempts=2, backoff_base_seconds=1.0, backoff_max_seconds=8.0),
        server_time_sync_enabled=True,
        server_time_resync_interval_seconds=300,
        max_server_time_offset_ms=5000,
        recv_window=10000,
    )


def _response(status_code: int, payload: dict) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("GET", "https://example.test/fapi/v2/positionRisk"),
    )


def test_signed_retry_rebuilds_timestamp_and_signature_after_1021(monkeypatch) -> None:
    notifier = DummyNotifier()
    client = BinanceClient(_settings(), notifier=notifier)
    fake_http = FakeHttpClient(
        [
            _response(400, {"code": -1021, "msg": "Timestamp for this request is outside of the recvWindow."}),
            _response(200, [{"symbol": "BTCUSDT", "positionAmt": "0"}]),
        ]
    )
    client.client = fake_http
    time_values = iter([1000.0, 1000.1, 1001.0, 1001.1, 1002.0, 1002.1])
    ensure_calls = []

    async def fake_ensure_time_sync(force=False):
        ensure_calls.append(force)
        if force:
            client.time_offset_ms = 250
        return True

    async def fake_sleep(_delay):
        return None

    monkeypatch.setattr("pump_system.exchange.binance_client.time.time", lambda: next(time_values))
    monkeypatch.setattr("pump_system.exchange.binance_client.asyncio.sleep", fake_sleep)
    client.ensure_time_sync = fake_ensure_time_sync

    result = asyncio.run(client.get_position_risk())

    assert result == [{"symbol": "BTCUSDT", "positionAmt": "0"}]
    assert len(fake_http.calls) == 2
    first_params = fake_http.calls[0][2]
    second_params = fake_http.calls[1][2]
    assert first_params["timestamp"] != second_params["timestamp"]
    assert first_params["signature"] != second_params["signature"]
    assert True in ensure_calls
    assert notifier.warning_events == []
