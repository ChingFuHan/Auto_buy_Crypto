from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime

from config import Settings
from pump_system.models import Kline
from pump_system.state.csv_state import AtomicCsvState


class StagingStore:
    """Keeps in-progress bars in local CSV and finalized bars in rolling memory."""

    FIELDNAMES = [
        "symbol",
        "interval",
        "open_time",
        "close_time",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
        "event_time",
    ]

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.interval = settings.strategy_interval
        self.logger = logging.getLogger("cache.staging")
        self._lock = asyncio.Lock()
        self._stores = {
            self.interval: AtomicCsvState(settings.strategy_staging_csv_path, self.FIELDNAMES),
        }
        self._in_progress: dict[str, dict[str, Kline]] = {self.interval: {}}
        self._history: dict[str, dict[str, deque[Kline]]] = {
            self.interval: defaultdict(lambda: deque(maxlen=settings.kline_seed_limit * 4)),
        }
        self._dirty: dict[str, bool] = {self.interval: False}

    async def load_runtime_state(self) -> None:
        """Restore last seen in-progress bars from CSV."""
        for interval, store in self._stores.items():
            rows = await store.load_rows()
            async with self._lock:
                for row in rows:
                    self._in_progress[interval][row["symbol"]] = self._row_to_kline(row)
        self.logger.info(
            "restored staging rows interval=%s rows=%s",
            self.interval,
            len(self._in_progress[self.interval]),
        )

    async def seed_finalized_bars(self, bars: list[Kline]) -> None:
        """Seed rolling memory from DB or REST catch-up."""
        async with self._lock:
            for bar in sorted(bars, key=lambda item: (item.symbol, item.interval, item.open_time)):
                self._upsert_history(bar.interval, bar)

    async def upsert_stream_kline(self, kline: Kline) -> Kline | None:
        """Update in-progress state and return finalized bar when the bar closes."""
        finalized: Kline | None = None
        async with self._lock:
            if kline.closed:
                finalized = kline
                self._upsert_history(kline.interval, kline)
                self._in_progress[kline.interval].pop(kline.symbol, None)
                self._dirty[kline.interval] = True
            else:
                self._in_progress[kline.interval][kline.symbol] = kline
                self._dirty[kline.interval] = True
        return finalized

    async def periodic_flush(self, stop_event: asyncio.Event) -> None:
        """Persist in-progress bars into dedicated CSV files."""
        while not stop_event.is_set():
            await asyncio.sleep(self.settings.staging_flush_interval_seconds)
            await self.flush_dirty()

    async def flush_dirty(self) -> None:
        for interval in self._stores:
            await self._flush_interval(interval)

    async def get_signal_snapshot(self, symbol: str, limit: int) -> tuple[list[Kline], Kline | None]:
        async with self._lock:
            history = list(self._history[self.interval].get(symbol, deque()))[-limit:]
            current = self._in_progress[self.interval].get(symbol)
            return history, current

    async def last_finalized_open_time(self, symbol: str, interval: str) -> datetime | None:
        async with self._lock:
            history = self._history[interval].get(symbol)
            return history[-1].open_time if history else None

    async def contract_trigger_price(self, symbol: str) -> tuple[str, object]:
        async with self._lock:
            current = self._in_progress[self.interval].get(symbol)
            if current is not None:
                return f"in_progress_{self.interval}_low", current.low_price
            history = self._history[self.interval].get(symbol)
            if history:
                return f"last_finalized_{self.interval}_close", history[-1].close_price
        return "missing", None

    def _upsert_history(self, interval: str, bar: Kline) -> None:
        history = self._history[interval][bar.symbol]
        if history and history[-1].open_time == bar.open_time:
            history[-1] = bar
            return
        history.append(bar)

    async def _flush_interval(self, interval: str) -> None:
        async with self._lock:
            if not self._dirty[interval]:
                return
            rows = [self._kline_to_row(bar) for bar in sorted(self._in_progress[interval].values(), key=lambda item: item.symbol)]
            self._dirty[interval] = False
        await self._stores[interval].replace_rows(rows)
        self.logger.info("staging csv flushed interval=%s rows=%s", interval, len(rows))

    @staticmethod
    def _kline_to_row(bar: Kline) -> dict[str, str]:
        return {
            "symbol": bar.symbol,
            "interval": bar.interval,
            "open_time": bar.open_time.isoformat(),
            "close_time": bar.close_time.isoformat(),
            "open_price": format(bar.open_price, "f"),
            "high_price": format(bar.high_price, "f"),
            "low_price": format(bar.low_price, "f"),
            "close_price": format(bar.close_price, "f"),
            "volume": format(bar.volume, "f"),
            "event_time": "" if bar.event_time is None else bar.event_time.isoformat(),
        }

    @staticmethod
    def _row_to_kline(row: dict[str, str]) -> Kline:
        from decimal import Decimal

        event_time = datetime.fromisoformat(row["event_time"]) if row["event_time"] else None
        return Kline(
            symbol=row["symbol"],
            interval=row["interval"],
            open_time=datetime.fromisoformat(row["open_time"]),
            close_time=datetime.fromisoformat(row["close_time"]),
            open_price=Decimal(row["open_price"]),
            high_price=Decimal(row["high_price"]),
            low_price=Decimal(row["low_price"]),
            close_price=Decimal(row["close_price"]),
            volume=Decimal(row["volume"]),
            closed=False,
            event_time=event_time,
        )
