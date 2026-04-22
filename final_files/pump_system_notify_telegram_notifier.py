from __future__ import annotations

import asyncio
import logging
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

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = logging.getLogger("notify.telegram")
        self.enabled = settings.telegram_configured
        self._requested = settings.telegram_enabled
        self._queue: asyncio.Queue[NotificationMessage | None] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None

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
        message = NotificationMessage(
            level=level,
            event_type=event_type,
            symbol=self._optional(kwargs.get("symbol")),
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
            item = await self._queue.get()
            if item is None:
                self._queue.task_done()
                break
            try:
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
                    self.logger.error("telegram send failed status=%s body=%s", response.status_code, response.text)
                else:
                    self.logger.info("telegram sent event_type=%s", item.event_type)
            except Exception as exc:
                self.logger.error("telegram send exception event_type=%s error=%s", item.event_type, exc)
            finally:
                self._queue.task_done()

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
