from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from config import Settings
from pump_system.models import utc_now


@dataclass(slots=True)
class NotificationMessage:
    level: str
    event_type: str
    symbol: str | None
    side: str | None
    quantity: str | None
    entry_price: str | None
    stop_price: str | None
    working_type: str | None
    order_id: str | None
    error_message: str | None
    details: dict[str, str]
    timestamp: datetime


class TelegramNotifier:
    """Queue-backed Telegram sender that never blocks the trading flow on failures."""

    MIN_SEND_INTERVAL_SECONDS = 1.0
    MAX_SENDS_PER_MINUTE = 20
    LOW_PRIORITY_QUEUE_LIMIT = 200
    MAX_DEFERRED_HIGH_PRIORITY = 100
    SIGNAL_DEDUPE_MAX = 1000

    LOW_PRIORITY_EVENTS = {
        "BACKFILL_STARTED",
        "BACKFILL_COMPLETED",
        "BINANCE_API_RETRY",
        "FUNCTION_TEST_MODE_SKIPPED_LIVE_ORDER",
        "HEARTBEAT",
        "SERVER_TIME_SYNC_OK",
        "SIGNAL_TRIGGERED",
        "SKIP_EXISTING_POSITION",
        "SKIP_MAX_CONCURRENT_POSITIONS",
        "SKIP_MIN_LEGAL_ORDER_UNREACHABLE",
        "TIME_OFFSET_WARNING",
        "WEBSOCKET_CATCHUP_COMPLETED",
        "WEBSOCKET_RECONNECTED",
    }

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = logging.getLogger("notify.telegram")
        self.enabled = settings.telegram_configured
        self._requested = settings.telegram_enabled
        self._queue: asyncio.Queue[NotificationMessage | None] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None
        self._flood_wait_until = 0.0
        self._sent_attempts: deque[float] = deque()
        self._signal_dedupe_keys: set[str] = set()
        self._signal_dedupe_order: deque[str] = deque()
        self._deferred_high_priority: dict[str, NotificationMessage] = {}

    async def start(self) -> None:
        """Start the background sender if Telegram is configured."""
        if not self._requested:
            return
        if not self.enabled:
            self.logger.warning("[ASSUMPTION] TELEGRAM_ENABLED=true but token/chat id missing; notifier disabled.")
            return
        if self._worker is not None:
            return
        self._client = httpx.AsyncClient(base_url="https://api.telegram.org", timeout=httpx.Timeout(15.0, connect=10.0))
        self._worker = asyncio.create_task(self._run())

    async def close(self) -> None:
        """Stop the worker and close the HTTP client."""
        if self._worker is not None:
            await self._queue.put(None)
            await self._worker
            self._worker = None
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def send_info(self, event_type: str, **kwargs: Any) -> None:
        await self._enqueue("INFO", event_type, **kwargs)

    async def send_warning(self, event_type: str, **kwargs: Any) -> None:
        await self._enqueue("WARN", event_type, **kwargs)

    async def send_error(self, event_type: str, **kwargs: Any) -> None:
        await self._enqueue("ERROR", event_type, **kwargs)

    async def send_trade(self, event_type: str, **kwargs: Any) -> None:
        await self._enqueue("TRADE", event_type, **kwargs)

    async def _enqueue(self, level: str, event_type: str, **kwargs: Any) -> None:
        if not self.enabled:
            return
        details = {
            key: self._stringify(value)
            for key, value in dict(kwargs.pop("details", {}) or {}).items()
            if value is not None and value != ""
        }
        symbol = self._optional(kwargs.get("symbol"))
        priority = self._priority(level, event_type)
        if self._flood_wait_remaining() > 0 and priority != "high":
            self.logger.warning(
                "telegram message dropped during flood wait event_type=%s remaining_seconds=%0.1f",
                event_type,
                self._flood_wait_remaining(),
            )
            return
        if priority == "low" and self._queue.qsize() >= self.LOW_PRIORITY_QUEUE_LIMIT:
            self.logger.warning(
                "telegram low priority message dropped due to queue pressure event_type=%s queue_size=%s",
                event_type,
                self._queue.qsize(),
            )
            return
        if event_type == "SIGNAL_TRIGGERED" and self._is_duplicate_signal(symbol, details):
            self.logger.info("telegram duplicate signal dropped symbol=%s key=%s", symbol, self._signal_dedupe_key(symbol, details))
            return
        message = NotificationMessage(
            level=level,
            event_type=event_type,
            symbol=symbol,
            side=self._optional(kwargs.get("side")),
            quantity=self._optional(kwargs.get("quantity")),
            entry_price=self._optional(kwargs.get("entry_price")),
            stop_price=self._optional(kwargs.get("stop_price")),
            working_type=self._optional(kwargs.get("working_type")),
            order_id=self._optional(kwargs.get("order_id")),
            error_message=self._optional(kwargs.get("error_message")),
            details=details,
            timestamp=kwargs.get("timestamp") or utc_now(),
        )
        await self._queue.put(message)

    async def _run(self) -> None:
        assert self._client is not None
        while True:
            wait_timeout = 1.0 if self._deferred_high_priority or self._flood_wait_remaining() > 0 else None
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=wait_timeout)
            except asyncio.TimeoutError:
                if self._flood_wait_remaining() <= 0:
                    try:
                        await self._send_deferred_high_priority()
                    except Exception as exc:
                        self.logger.error("telegram deferred send exception error=%s", exc)
                continue
            if item is None:
                self._queue.task_done()
                break
            try:
                if self._flood_wait_remaining() > 0:
                    if self._priority(item.level, item.event_type) == "high":
                        self._defer_high_priority(item, reason="flood_wait")
                    else:
                        self.logger.warning(
                            "telegram queued message dropped during flood wait event_type=%s remaining_seconds=%0.1f",
                            item.event_type,
                            self._flood_wait_remaining(),
                        )
                    continue
                await self._send_deferred_high_priority()
                if self._flood_wait_remaining() <= 0:
                    await self._send_one(item)
            except Exception as exc:
                self.logger.error("telegram send exception event_type=%s error=%s", item.event_type, exc)
            finally:
                self._queue.task_done()

    async def _send_deferred_high_priority(self) -> None:
        if not self._deferred_high_priority:
            return
        deferred = list(self._deferred_high_priority.values())
        self._deferred_high_priority.clear()
        for item in deferred:
            if self._flood_wait_remaining() > 0:
                self._defer_high_priority(item, reason="flood_wait_resumed")
                return
            await self._send_one(item)

    async def _send_one(self, item: NotificationMessage) -> None:
        assert self._client is not None
        await self._wait_for_rate_limit()
        text = self.build_message(
            level=item.level,
            event_type=item.event_type,
            timestamp=item.timestamp,
            symbol=item.symbol,
            side=item.side,
            quantity=item.quantity,
            entry_price=item.entry_price,
            stop_price=item.stop_price,
            working_type=item.working_type,
            order_id=item.order_id,
            error_message=item.error_message,
            details=item.details,
        )
        response = await self._client.post(
            f"/bot{self.settings.telegram_bot_token}/sendMessage",
            json={
                "chat_id": self.settings.telegram_chat_id,
                "text": text,
                "disable_notification": item.level == "INFO",
            },
        )
        if response.status_code >= 400:
            self._handle_send_failure(response, item)
            return
        self.logger.info("telegram sent event_type=%s", item.event_type)

    async def _wait_for_rate_limit(self) -> None:
        while True:
            now = time.monotonic()
            while self._sent_attempts and now - self._sent_attempts[0] >= 60:
                self._sent_attempts.popleft()
            waits: list[float] = []
            if self._sent_attempts:
                waits.append(self.MIN_SEND_INTERVAL_SECONDS - (now - self._sent_attempts[-1]))
            if len(self._sent_attempts) >= self.MAX_SENDS_PER_MINUTE:
                waits.append(60 - (now - self._sent_attempts[0]))
            wait_seconds = max([value for value in waits if value > 0], default=0)
            if wait_seconds <= 0:
                self._sent_attempts.append(time.monotonic())
                return
            await asyncio.sleep(min(wait_seconds, 1.0))

    def _handle_send_failure(self, response: httpx.Response, item: NotificationMessage) -> None:
        retry_after = self._extract_retry_after_seconds(response)
        if response.status_code == 429 and retry_after is not None:
            self._flood_wait_until = max(self._flood_wait_until, time.monotonic() + retry_after)
            self.logger.error(
                "telegram send failed status=429 retry_after_seconds=%s event_type=%s body=%s",
                retry_after,
                item.event_type,
                response.text,
            )
            if self._priority(item.level, item.event_type) == "high":
                self._defer_high_priority(item, reason="telegram_429")
            return
        self.logger.error("telegram send failed status=%s body=%s", response.status_code, response.text)

    @staticmethod
    def _extract_retry_after_seconds(response: httpx.Response) -> int | None:
        try:
            data = response.json()
        except json.JSONDecodeError:
            return None
        parameters = data.get("parameters")
        if not isinstance(parameters, dict):
            return None
        retry_after = parameters.get("retry_after")
        try:
            return int(retry_after)
        except (TypeError, ValueError):
            return None

    def _flood_wait_remaining(self) -> float:
        return max(0.0, self._flood_wait_until - time.monotonic())

    @classmethod
    def _priority(cls, level: str, event_type: str) -> str:
        if event_type in cls.LOW_PRIORITY_EVENTS:
            return "low"
        if level in {"TRADE", "ERROR"}:
            return "high"
        return "normal"

    def _defer_high_priority(self, item: NotificationMessage, reason: str) -> None:
        key = self._deferred_key(item)
        if len(self._deferred_high_priority) >= self.MAX_DEFERRED_HIGH_PRIORITY and key not in self._deferred_high_priority:
            dropped_key = next(iter(self._deferred_high_priority))
            self._deferred_high_priority.pop(dropped_key, None)
            self.logger.error("telegram deferred high priority message dropped due to cap key=%s", dropped_key)
        self._deferred_high_priority[key] = item
        self.logger.warning(
            "telegram high priority message deferred event_type=%s reason=%s deferred_count=%s",
            item.event_type,
            reason,
            len(self._deferred_high_priority),
        )

    @staticmethod
    def _deferred_key(item: NotificationMessage) -> str:
        return "|".join(
            (
                item.event_type,
                item.symbol or "",
                item.order_id or "",
                item.side or "",
                item.entry_price or "",
                item.stop_price or "",
            )
        )

    def _is_duplicate_signal(self, symbol: str | None, details: dict[str, str]) -> bool:
        key = self._signal_dedupe_key(symbol, details)
        if key is None:
            return False
        if key in self._signal_dedupe_keys:
            return True
        self._signal_dedupe_keys.add(key)
        self._signal_dedupe_order.append(key)
        while len(self._signal_dedupe_order) > self.SIGNAL_DEDUPE_MAX:
            old_key = self._signal_dedupe_order.popleft()
            self._signal_dedupe_keys.discard(old_key)
        return False

    @staticmethod
    def _signal_dedupe_key(symbol: str | None, details: dict[str, str]) -> str | None:
        bar_key = details.get("bar_key") or details.get("bar_open_time")
        if not symbol or not bar_key:
            return None
        return f"{symbol}:{bar_key}"

    @staticmethod
    def build_message(
        *,
        level: str,
        event_type: str,
        timestamp: datetime,
        symbol: str | None = None,
        side: str | None = None,
        quantity: str | None = None,
        entry_price: str | None = None,
        stop_price: str | None = None,
        working_type: str | None = None,
        order_id: str | None = None,
        error_message: str | None = None,
        details: dict[str, str] | None = None,
    ) -> str:
        """Build a concise Telegram text payload with the required audit fields."""
        lines = [
            f"[{level}] {event_type}",
            f"timestamp: {timestamp.isoformat()}",
        ]
        optional_pairs = [
            ("symbol", symbol),
            ("side", side),
            ("quantity", quantity),
            ("entry_price", entry_price),
            ("stop_price", stop_price),
            ("workingType", working_type),
            ("order_id", order_id),
            ("error", error_message),
        ]
        for label, value in optional_pairs:
            if value:
                lines.append(f"{label}: {value}")
        for key, value in (details or {}).items():
            lines.append(f"{key}: {value}")
        return "\n".join(lines)

    @staticmethod
    def _stringify(value: Any) -> str:
        if isinstance(value, Decimal):
            return format(value, "f")
        return str(value)

    @classmethod
    def _optional(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        return cls._stringify(value)
