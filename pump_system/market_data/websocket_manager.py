from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import websockets

from config import Settings

if TYPE_CHECKING:
    from pump_system.notify.telegram_notifier import TelegramNotifier


class WebSocketManager:
    """Combined-stream websocket consumer with bounded reconnects."""

    def __init__(
        self,
        settings: Settings,
        on_kline: Callable[[dict], Awaitable[None]],
        on_reconnect: Callable[[list[str]], Awaitable[None]],
        notifier: "TelegramNotifier | None" = None,
    ) -> None:
        self.settings = settings
        self.on_kline = on_kline
        self.on_reconnect = on_reconnect
        self.notifier = notifier
        self.logger = logging.getLogger("market_data.websocket")
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    async def start(self, symbols: list[str]) -> None:
        await self.stop()
        self._stop_event = asyncio.Event()
        streams: list[str] = []
        for symbol in symbols:
            lower = symbol.lower()
            streams.append(f"{lower}@kline_3m")

        chunk_size = max(1, min(self.settings.ws_max_streams_per_connection, 1024))
        for index in range(0, len(streams), chunk_size):
            chunk = streams[index : index + chunk_size]
            self._tasks.append(asyncio.create_task(self._run_chunk(chunk)))

    async def stop(self) -> None:
        self._stop_event.set()
        if not self._tasks:
            return
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    async def restart(self, symbols: list[str]) -> None:
        await self.start(symbols)

    async def _run_chunk(self, streams: list[str]) -> None:
        symbols = sorted({stream.split("@", 1)[0].upper() for stream in streams})
        url = f"{self.settings.ws_base_url}/stream?streams={'/'.join(streams)}"
        attempt = 0
        while not self._stop_event.is_set():
            try:
                self.logger.info("websocket connect symbols=%s streams=%s", len(symbols), len(streams))
                async with websockets.connect(url, ping_interval=150, ping_timeout=30, close_timeout=10) as websocket:
                    if attempt > 0:
                        await self.on_reconnect(symbols)
                        if self.notifier is not None:
                            await self.notifier.send_info(
                                "WEBSOCKET_RECONNECTED",
                                details={"symbol_count": len(symbols), "stream_count": len(streams)},
                            )
                    attempt = 0
                    async for raw_message in websocket:
                        payload = json.loads(raw_message)
                        data = payload.get("data", payload)
                        if data.get("e") == "kline":
                            await self.on_kline(data)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                attempt += 1
                if attempt >= self.settings.ws_max_reconnect_attempts:
                    self.logger.error("[BLOCKED] websocket exceeded retries symbols=%s error=%s", len(symbols), exc)
                    if self.notifier is not None:
                        await self.notifier.send_error(
                            "WEBSOCKET_RECONNECT_BLOCKED",
                            error_message=str(exc),
                            details={
                                "symbol_count": len(symbols),
                                "stream_count": len(streams),
                                "attempt": f"{attempt}/{self.settings.ws_max_reconnect_attempts}",
                            },
                        )
                    return
                delay = min(2 ** (attempt - 1), 8)
                self.logger.warning(
                    "websocket reconnect symbols=%s attempt=%s/%s delay=%ss error=%s",
                    len(symbols),
                    attempt,
                    self.settings.ws_max_reconnect_attempts,
                    delay,
                    exc,
                )
                if self.notifier is not None:
                    await self.notifier.send_warning(
                        "WEBSOCKET_RECONNECTING",
                        error_message=str(exc),
                        details={
                            "symbol_count": len(symbols),
                            "stream_count": len(streams),
                            "attempt": f"{attempt}/{self.settings.ws_max_reconnect_attempts}",
                            "delay_seconds": delay,
                        },
                    )
                await asyncio.sleep(delay)
