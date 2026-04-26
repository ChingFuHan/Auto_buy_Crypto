from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from config import Settings
from pump_system.cache.staging_store import StagingStore
from pump_system.db.repository import KlineRepository
from pump_system.exchange.binance_client import BinanceClient
from pump_system.models import Kline

if TYPE_CHECKING:
    from pump_system.notify.telegram_notifier import TelegramNotifier


UTC = timezone.utc


class BackfillService:
    """REST backfill for 90-day finalized 3m futures klines."""

    TABLE_BY_INTERVAL = {
        "3m": "public.semi_auto_price_future_3m",
    }
    INTERVAL_MS = {"3m": 180_000}

    def __init__(
        self,
        settings: Settings,
        exchange_client: BinanceClient,
        repository: KlineRepository,
        staging_store: StagingStore,
        notifier: "TelegramNotifier | None" = None,
    ) -> None:
        self.settings = settings
        self.exchange_client = exchange_client
        self.repository = repository
        self.staging_store = staging_store
        self.notifier = notifier
        self.logger = logging.getLogger("market_data.backfill")

    async def backfill_universe(self, symbols: list[str]) -> None:
        """Backfill all USDT perpetual symbols for 3m without overwriting history."""
        if not symbols:
            return
        if self.notifier is not None:
            await self.notifier.send_info(
                "BACKFILL_STARTED",
                details={
                    "symbol_count": len(symbols),
                    "intervals": "3m",
                    "backfill_days": self.settings.backfill_days,
                },
            )
        server_now_ms = int(time.time() * 1000) + self.exchange_client.time_offset_ms
        start_cutoff = server_now_ms - self.settings.backfill_days * 24 * 60 * 60 * 1000
        latest_map = {
            interval: self.repository.fetch_latest_timestamps(table)
            for interval, table in self.TABLE_BY_INTERVAL.items()
        }
        semaphore = asyncio.Semaphore(self.settings.backfill_concurrency)

        async def runner(symbol: str, interval: str) -> int:
            async with semaphore:
                table_name = self.TABLE_BY_INTERVAL[interval]
                existing_da = latest_map[interval].get(symbol)
                if existing_da is None:
                    start_ms = start_cutoff
                else:
                    start_ms = int(existing_da.replace(tzinfo=UTC).timestamp() * 1000) + self.INTERVAL_MS[interval]
                    start_ms = max(start_ms, start_cutoff)
                return await self._backfill_symbol_interval(symbol, interval, table_name, start_ms, server_now_ms)

        tasks = [
            asyncio.create_task(runner(symbol, interval))
            for symbol in symbols
            for interval in self.TABLE_BY_INTERVAL
        ]
        inserted_counts = await asyncio.gather(*tasks)
        total_inserted = sum(inserted_counts)
        if self.notifier is not None:
            await self.notifier.send_info(
                "BACKFILL_COMPLETED",
                details={
                    "symbol_count": len(symbols),
                    "intervals": "3m",
                    "inserted_rows": total_inserted,
                },
            )

    async def catch_up_symbols(self, symbols: list[str]) -> None:
        """Fetch missed finalized bars after websocket reconnect using staging memory."""
        if not symbols:
            return
        server_now_ms = int(time.time() * 1000) + self.exchange_client.time_offset_ms
        for symbol in symbols:
            for interval in self.TABLE_BY_INTERVAL:
                last_open = await self.staging_store.last_finalized_open_time(symbol, interval)
                if last_open is None:
                    continue
                start_ms = int(last_open.timestamp() * 1000) + self.INTERVAL_MS[interval]
                await self._backfill_symbol_interval(
                    symbol,
                    interval,
                    self.TABLE_BY_INTERVAL[interval],
                    start_ms,
                    server_now_ms,
                    seed_staging=True,
                )

    async def _backfill_symbol_interval(
        self,
        symbol: str,
        interval: str,
        table_name: str,
        start_ms: int,
        server_now_ms: int,
        seed_staging: bool = False,
    ) -> int:
        interval_ms = self.INTERVAL_MS[interval]
        current_open_ms = (server_now_ms // interval_ms) * interval_ms
        if start_ms >= current_open_ms:
            return 0

        batch_total = 0
        while start_ms < current_open_ms:
            rows = await self.exchange_client.get_klines(
                symbol=symbol,
                interval=interval,
                start_time=start_ms,
                end_time=current_open_ms - 1,
                limit=self.settings.backfill_limit,
            )
            bars = [self._rest_row_to_kline(symbol, interval, row) for row in rows if int(row[6]) < current_open_ms]
            if not bars:
                break

            inserted = self.repository.bulk_insert_klines(table_name, bars)
            if seed_staging:
                await self.staging_store.seed_finalized_bars(bars)
            batch_total += inserted
            start_ms = int(rows[-1][0]) + interval_ms
            if len(rows) < self.settings.backfill_limit:
                break

        if batch_total:
            self.logger.info("backfill completed symbol=%s interval=%s inserted=%s", symbol, interval, batch_total)
        return batch_total

    @staticmethod
    def _rest_row_to_kline(symbol: str, interval: str, row: list) -> Kline:
        return Kline(
            symbol=symbol,
            interval=interval,
            open_time=datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC),
            close_time=datetime.fromtimestamp(int(row[6]) / 1000, tz=UTC),
            open_price=Decimal(str(row[1])),
            high_price=Decimal(str(row[2])),
            low_price=Decimal(str(row[3])),
            close_price=Decimal(str(row[4])),
            volume=Decimal(str(row[5])),
            closed=True,
            event_time=None,
        )
