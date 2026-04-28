from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from dataclasses import asdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import httpx

from config import Settings
from pump_system.utils.retry import RetryPolicy

if TYPE_CHECKING:
    from pump_system.notify.telegram_notifier import TelegramNotifier


class BinanceAPIError(Exception):
    """Raised when Binance returns a non-retryable error."""


class BinanceClient:
    """Async Binance USD-M Futures REST client with bounded retries and time sync."""

    def __init__(self, settings: Settings, notifier: "TelegramNotifier | None" = None) -> None:
        self.settings = settings
        self.notifier = notifier
        self.logger = logging.getLogger("exchange.binance")
        self.retry_policy = RetryPolicy(**asdict(settings.retry))
        headers = {}
        if settings.api_key:
            headers["X-MBX-APIKEY"] = settings.api_key
        self.client = httpx.AsyncClient(
            base_url=settings.rest_base_url,
            timeout=httpx.Timeout(20.0, connect=10.0),
            headers=headers,
        )
        self.time_offset_ms = 0
        self.last_sync_epoch_ms = 0
        self.last_sync_rtt_ms = 0
        self.rate_limit_wait_until_ms = 0.0

    @property
    def has_private_api(self) -> bool:
        return bool(self.settings.api_key and self.settings.api_secret)

    async def close(self) -> None:
        await self.client.aclose()

    async def sync_server_time(self) -> int:
        """Sync local clock against Binance server time using midpoint estimation."""
        local_before = int(time.time() * 1000)
        response = await self._request("GET", "/fapi/v1/time", signed=False)
        local_after = int(time.time() * 1000)
        server_time = int(response["serverTime"])
        midpoint = (local_before + local_after) // 2
        self.time_offset_ms = server_time - midpoint
        self.last_sync_epoch_ms = local_after
        self.last_sync_rtt_ms = local_after - local_before
        self.logger.info(
            "server time synced offset_ms=%s rtt_ms=%s",
            self.time_offset_ms,
            self.last_sync_rtt_ms,
        )
        return self.time_offset_ms

    async def ensure_time_sync(self, force: bool = False) -> bool:
        if not self.settings.server_time_sync_enabled:
            return True

        now_ms = int(time.time() * 1000)
        stale = now_ms - self.last_sync_epoch_ms >= self.settings.server_time_resync_interval_seconds * 1000
        if force or self.last_sync_epoch_ms == 0 or stale:
            await self.sync_server_time()

        if abs(self.time_offset_ms) > self.settings.max_server_time_offset_ms:
            self.logger.error(
                "[BLOCKED] server time offset too large offset_ms=%s threshold_ms=%s",
                self.time_offset_ms,
                self.settings.max_server_time_offset_ms,
            )
            if self.notifier is not None:
                await self.notifier.send_error(
                    "SERVER_TIME_OFFSET_BLOCKED",
                    error_message="offset_exceeded_threshold",
                    details={
                        "offset_ms": self.time_offset_ms,
                        "threshold_ms": self.settings.max_server_time_offset_ms,
                    },
                )
            return False
        return True

    async def get_exchange_info(self) -> dict[str, Any]:
        return await self._request("GET", "/fapi/v1/exchangeInfo", signed=False)

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 1000,
    ) -> list[list[Any]]:
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        data = await self._request("GET", "/fapi/v1/klines", signed=False, params=params)
        return list(data)

    async def get_latest_kline(self, symbol: str, interval: str) -> list[Any]:
        """Fetch the latest REST kline snapshot, which may still be in progress."""
        rows = await self.get_klines(symbol=symbol, interval=interval, limit=1)
        if not rows:
            raise BinanceAPIError(f"latest_kline_missing symbol={symbol} interval={interval}")
        return rows[-1]

    async def get_account_info(self) -> dict[str, Any]:
        return await self._request("GET", "/fapi/v2/account", signed=True)

    async def get_position_risk(self, symbol: str | None = None) -> list[dict[str, Any]]:
        params = {"symbol": symbol} if symbol else {}
        data = await self._request("GET", "/fapi/v2/positionRisk", signed=True, params=params)
        if isinstance(data, dict):
            return [data]
        return list(data)

    async def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        params = {"symbol": symbol} if symbol else {}
        data = await self._request("GET", "/fapi/v1/openOrders", signed=True, params=params)
        return list(data)

    async def get_leverage_bracket(self, symbol: str) -> dict[str, Any]:
        data = await self._request("GET", "/fapi/v1/leverageBracket", signed=True, params={"symbol": symbol})
        if isinstance(data, list):
            if not data:
                raise BinanceAPIError(f"leverage_bracket_empty symbol={symbol}")
            return dict(data[0])
        return dict(data)

    async def set_margin_type(self, symbol: str, margin_type: str = "CROSSED") -> dict[str, Any]:
        try:
            return await self._request(
                "POST",
                "/fapi/v1/marginType",
                signed=True,
                params={"symbol": symbol, "marginType": margin_type},
            )
        except BinanceAPIError as exc:
            if "No need to change margin type" in str(exc):
                return {"code": 200, "msg": "already_crossed"}
            raise

    async def set_leverage(self, symbol: str, leverage: int) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/fapi/v1/leverage",
            signed=True,
            params={"symbol": symbol, "leverage": leverage},
        )

    async def create_order(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/fapi/v1/order", signed=True, params=params)

    async def create_algo_order(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/fapi/v1/algoOrder", signed=True, params=params)

    async def create_conditional_order(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/fapi/v1/takeProfitAndStopLoss", signed=True, params=params)

    async def get_open_algo_orders(
        self,
        symbol: str | None = None,
        algo_type: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        if algo_type:
            params["algoType"] = algo_type
        data = await self._request("GET", "/fapi/v1/openAlgoOrders", signed=True, params=params)
        return list(data)

    async def get_all_orders(self, symbol: str, limit: int = 20) -> list[dict[str, Any]]:
        data = await self._request("GET", "/fapi/v1/allOrders", signed=True, params={"symbol": symbol, "limit": limit})
        return list(data)

    async def get_mark_price(self, symbol: str) -> Decimal:
        data = await self._request("GET", "/fapi/v1/premiumIndex", signed=False, params={"symbol": symbol})
        return Decimal(str(data["markPrice"]))

    async def _request(
        self,
        method: str,
        path: str,
        signed: bool,
        params: dict[str, Any] | None = None,
    ) -> Any:
        params = dict(params or {})
        params = self._normalize_params(params)
        if signed:
            if not self.has_private_api:
                raise BinanceAPIError("missing_api_credentials")
            if not await self.ensure_time_sync():
                raise BinanceAPIError("timestamp_unhealthy")
            params["recvWindow"] = self.settings.recv_window
            params["timestamp"] = int(time.time() * 1000) + self.time_offset_ms
            params["signature"] = self._sign(params)

        for attempt in range(1, self.retry_policy.max_attempts + 1):
            now_ms = time.time() * 1000

            # Check if we're still in rate limit wait window
            if self.rate_limit_wait_until_ms > now_ms:
                remaining_ms = self.rate_limit_wait_until_ms - now_ms
                wait_sec = remaining_ms / 1000.0
                self.logger.warning(
                    "rate limit 429 detected, waiting %0.1f sec until next minute method=%s path=%s",
                    wait_sec,
                    method,
                    path,
                )
                if self.notifier is not None:
                    await self.notifier.send_warning(
                        "BINANCE_API_RATE_LIMIT_WAIT",
                        error_message=f"Rate limited. Waiting {wait_sec:.1f}s before retry.",
                        details={
                            "method": method,
                            "path": path,
                            "wait_seconds": f"{wait_sec:.1f}",
                        },
                    )
                await asyncio.sleep(wait_sec + 0.5)
                continue

            try:
                response = await self.client.request(method, path, params=params)
                data = self._decode_response(response)
                if response.status_code >= 400:
                    raise self._to_error(response.status_code, data)
                return data
            except (httpx.HTTPError, BinanceAPIError) as exc:
                is_rate_limit = "status=429" in str(exc)
                retryable = self._is_retryable(exc)

                if is_rate_limit:
                    now_ms = time.time() * 1000
                    self.rate_limit_wait_until_ms = now_ms + 60_000

                    remaining_ms = max(0, self.rate_limit_wait_until_ms - now_ms)
                    wait_sec = remaining_ms / 1000.0
                    self.logger.warning(
                        "rate limit 429 detected, waiting %0.1f sec until next minute method=%s path=%s error=%s",
                        wait_sec,
                        method,
                        path,
                        exc,
                    )
                    if self.notifier is not None:
                        await self.notifier.send_warning(
                            "BINANCE_API_RATE_LIMIT_WAIT",
                            error_message=f"Rate limited. Waiting {wait_sec:.1f}s before retry.",
                            details={
                                "method": method,
                                "path": path,
                                "wait_seconds": f"{wait_sec:.1f}",
                            },
                        )
                    await asyncio.sleep(wait_sec + 0.5)
                    continue

                if attempt >= self.retry_policy.max_attempts or not retryable:
                    self.logger.error(
                        "request failed method=%s path=%s attempt=%s/%s error=%s",
                        method,
                        path,
                        attempt,
                        self.retry_policy.max_attempts,
                        exc,
                    )
                    if self.notifier is not None and retryable:
                        await self.notifier.send_error(
                            "BINANCE_API_BLOCKED",
                            error_message=str(exc),
                            details={
                                "method": method,
                                "path": path,
                                "attempt": f"{attempt}/{self.retry_policy.max_attempts}",
                            },
                        )
                    raise

                delay = self.retry_policy.delay_for_attempt(attempt)
                self.logger.warning(
                    "request retry method=%s path=%s attempt=%s/%s delay=%ss error=%s",
                    method,
                    path,
                    attempt,
                    self.retry_policy.max_attempts,
                    delay,
                    exc,
                )
                if self.notifier is not None and self._is_retryable(exc):
                    await self.notifier.send_warning(
                        "BINANCE_API_RETRY",
                        error_message=str(exc),
                        details={
                            "method": method,
                            "path": path,
                            "attempt": f"{attempt}/{self.retry_policy.max_attempts}",
                            "delay_seconds": delay,
                        },
                    )
                await self.ensure_time_sync(force=isinstance(exc, BinanceAPIError) and "1021" in str(exc))
                await asyncio.sleep(delay)

        raise BinanceAPIError("unexpected_retry_exit")

    def _sign(self, params: dict[str, Any]) -> str:
        query = urlencode(self._normalize_params(params))
        return hmac.new(
            self.settings.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _normalize_params(params: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in params.items():
            if isinstance(value, Decimal):
                normalized[key] = format(value, "f")
            elif isinstance(value, bool):
                normalized[key] = "true" if value else "false"
            else:
                normalized[key] = value
        return normalized

    @staticmethod
    def _decode_response(response: httpx.Response) -> Any:
        if not response.text:
            return {}
        try:
            return response.json()
        except json.JSONDecodeError:
            return {"msg": response.text}

    @staticmethod
    def _to_error(status_code: int, data: Any) -> BinanceAPIError:
        if isinstance(data, dict):
            code = data.get("code")
            msg = data.get("msg", "")
            return BinanceAPIError(f"status={status_code} code={code} msg={msg}")
        return BinanceAPIError(f"status={status_code} body={data}")

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, httpx.HTTPError):
            return True
        message = str(exc)
        retry_markers = ("status=429", "status=418", "status=500", "status=502", "status=503", "status=504")
        api_markers = ("code=-1001", "code=-1021", "code=-1007")
        return any(marker in message for marker in retry_markers + api_markers)
