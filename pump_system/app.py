from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal

from config import Settings
from pump_system.cache.staging_store import StagingStore
from pump_system.db.repository import KlineRepository
from pump_system.exchange.binance_client import BinanceClient
from pump_system.exchange.symbol_registry import SymbolRegistry
from pump_system.execution.order_service import OrderService
from pump_system.fallback_stop.manager import FallbackStopManager
from pump_system.market_data.backfill import BackfillService
from pump_system.market_data.websocket_manager import WebSocketManager
from pump_system.models import Kline
from pump_system.notify.telegram_notifier import TelegramNotifier
from pump_system.state.position_state import PositionState
from pump_system.strategy.signal_engine import SignalEngine
from pump_system.sync.time_sync_manager import TimeSyncManager
from pump_system.utils.logging_utils import configure_logging


UTC = timezone.utc


def _format_uptime(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class TradingApplication:
    """Main application composition root."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        configure_logging(settings.log_dir, settings.log_level)
        self.logger = logging.getLogger("app")
        self.notifier = TelegramNotifier(settings)
        self.exchange_client = BinanceClient(settings, notifier=self.notifier)
        self.repository = KlineRepository(settings.db_name)
        self.symbol_registry = SymbolRegistry(settings)
        self.staging_store = StagingStore(settings)
        self.position_state = PositionState(self.exchange_client)
        self.signal_engine = SignalEngine(settings.strategy)
        self.fallback_manager = FallbackStopManager(
            settings,
            self.exchange_client,
            self.position_state,
            self.staging_store,
            notifier=self.notifier,
        )
        self.backfill_service = BackfillService(
            settings,
            self.exchange_client,
            self.repository,
            self.staging_store,
            notifier=self.notifier,
        )
        self.order_service = OrderService(
            settings=settings,
            exchange_client=self.exchange_client,
            symbol_registry=self.symbol_registry,
            staging_store=self.staging_store,
            position_state=self.position_state,
            signal_engine=self.signal_engine,
            fallback_manager=self.fallback_manager,
            notifier=self.notifier,
        )
        self.websocket_manager = WebSocketManager(
            settings=settings,
            on_kline=self._handle_kline_payload,
            on_reconnect=self._handle_reconnect,
            notifier=self.notifier,
        )
        self.time_sync_manager = TimeSyncManager(
            exchange_client=self.exchange_client,
            notifier=self.notifier,
            resync_interval_seconds=settings.server_time_resync_interval_seconds,
            warning_threshold_ms=3000,
            critical_threshold_ms=8000,
        )
        self.stop_event = asyncio.Event()
        self.background_tasks: list[asyncio.Task] = []
        self._pending_finalized: dict[str, list[Kline]] = {self.settings.strategy_interval: []}
        self._pending_lock = asyncio.Lock()
        self._db_flush_failures: dict[str, int] = {self.settings.strategy_interval: 0}
        self._app_started_monotonic: float | None = None

    async def validate_only(self) -> None:
        try:
            await self._bootstrap(run_backfill=False)
            self.logger.info("validation bootstrap completed")
        except Exception as exc:
            self.logger.error("[BLOCKED] validate bootstrap failed error=%s", exc)
            await self.notifier.send_error("VALIDATE_BOOTSTRAP_FAILED", error_message=str(exc))
            raise
        finally:
            await self.shutdown()

    async def backfill_only(self) -> None:
        try:
            await self._bootstrap(run_backfill=True)
        except Exception as exc:
            self.logger.error("[BLOCKED] backfill bootstrap failed error=%s", exc)
            await self.notifier.send_error("BACKFILL_BOOTSTRAP_FAILED", error_message=str(exc))
            raise
        finally:
            await self.shutdown()

    async def manual_test_entry(self) -> None:
        try:
            await self._bootstrap(run_backfill=False)
            await self.order_service.execute_manual_function_test()
            self.logger.info("[INFO] manual test entry completed, keeping app running for stop monitoring")
            self._start_background_tasks()
            await self.stop_event.wait()
        except Exception as exc:
            self.logger.error("[BLOCKED] manual function test failed error=%s", exc)
            await self.notifier.send_error("MANUAL_FUNCTION_TEST_FAILED", error_message=str(exc))
            raise
        finally:
            await self.shutdown()

    async def run(self) -> None:
        try:
            await self._bootstrap(run_backfill=self.settings.startup_backfill_enabled)
            await self.websocket_manager.start(sorted(self.symbol_registry.data_symbols))
            self._start_background_tasks()
            await self.stop_event.wait()
        except KeyboardInterrupt:
            self.logger.info("shutdown requested by keyboard interrupt")
        except Exception as exc:
            self.logger.error("[BLOCKED] application run failed error=%s", exc)
            await self.notifier.send_error("APPLICATION_RUN_BLOCKED", error_message=str(exc))
            raise
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        self.stop_event.set()
        for task in self.background_tasks:
            task.cancel()
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        self.background_tasks.clear()
        await self.websocket_manager.stop()
        await self._flush_finalized_batches()
        await self.staging_store.flush_dirty()
        await self.notifier.send_info("APP_SHUTDOWN")
        await self.exchange_client.close()
        await self.notifier.close()

    async def _bootstrap(self, run_backfill: bool) -> None:
        await self.notifier.start()
        self.repository.healthcheck()
        await self.staging_store.load_runtime_state()
        await self.fallback_manager.load_existing()
        time_sync_ok = await self.exchange_client.ensure_time_sync(force=True)
        if time_sync_ok:
            await self.notifier.send_info(
                "SERVER_TIME_SYNC_OK",
                details={
                    "offset_ms": self.exchange_client.time_offset_ms,
                    "rtt_ms": self.exchange_client.last_sync_rtt_ms,
                },
            )
        exchange_info = await self.exchange_client.get_exchange_info()
        self.symbol_registry.refresh_from_exchange_info(exchange_info)
        self.logger.info(
            "symbol registry loaded data_symbols=%s candidate_symbols=%s",
            len(self.symbol_registry.data_symbols),
            len(self.symbol_registry.candidate_symbols),
        )
        if self.exchange_client.has_private_api:
            await self.position_state.refresh()
            await self.order_service.restore_native_stop_watchlist()
        if run_backfill:
            await self.backfill_service.backfill_universe(sorted(self.symbol_registry.data_symbols))
        await self._seed_strategy_history()
        await self._send_startup_notifications()

    def _start_background_tasks(self) -> None:
        self._app_started_monotonic = time.monotonic()
        self.background_tasks = [
            asyncio.create_task(self.staging_store.periodic_flush(self.stop_event)),
            asyncio.create_task(self.fallback_manager.run(self.stop_event)),
            asyncio.create_task(self.order_service.run_native_stop_monitor(self.stop_event)),
            asyncio.create_task(self.time_sync_manager.run(self.stop_event)),
            asyncio.create_task(self._position_refresh_loop()),
            asyncio.create_task(self._symbol_refresh_loop()),
            asyncio.create_task(self._db_flush_loop()),
            asyncio.create_task(self._heartbeat_loop()),
        ]

    async def _handle_kline_payload(self, payload: dict) -> None:
        kline = self._parse_ws_kline(payload)
        finalized = await self.staging_store.upsert_stream_kline(kline)
        if finalized is not None:
            async with self._pending_lock:
                self._pending_finalized[finalized.interval].append(finalized)
            await self.staging_store.flush_dirty()
            self.logger.info("finalized bar buffered symbol=%s interval=%s", finalized.symbol, finalized.interval)
        else:
            self.logger.info("staging updated symbol=%s interval=%s", kline.symbol, kline.interval)

        if self.symbol_registry.should_evaluate(kline.symbol):
            await self.order_service.on_market_update(kline.symbol)

    async def _handle_reconnect(self, symbols: list[str]) -> None:
        self.logger.info("websocket reconnected, catching up symbols=%s", len(symbols))
        await self.backfill_service.catch_up_symbols(symbols)
        await self.notifier.send_info("WEBSOCKET_CATCHUP_COMPLETED", details={"symbol_count": len(symbols)})

    async def _server_time_loop(self) -> None:
        """已移轉至 TimeSyncManager - 此方法保留以便向後相容"""
        while not self.stop_event.is_set():
            await asyncio.sleep(self.settings.server_time_resync_interval_seconds)

    async def _position_refresh_loop(self) -> None:
        while not self.stop_event.is_set():
            await asyncio.sleep(self.settings.position_refresh_interval_seconds)
            if not self.exchange_client.has_private_api:
                continue
            try:
                await self.position_state.refresh()
                self.logger.info(
                    "position sync complete positions=%s open_order_symbols=%s",
                    self.position_state.active_position_count(),
                    len(self.position_state.open_order_counts),
                )
            except Exception as exc:
                self.logger.error("position sync failed error=%s", exc)

    async def _symbol_refresh_loop(self) -> None:
        while not self.stop_event.is_set():
            await asyncio.sleep(self.settings.symbol_refresh_interval_seconds)
            try:
                exchange_info = await self.exchange_client.get_exchange_info()
                result = self.symbol_registry.refresh_from_exchange_info(exchange_info)
                if result.data_symbols_changed:
                    added = sorted(result.current_data_symbols - result.previous_data_symbols)
                    if added:
                        await self.backfill_service.backfill_universe(added)
                    await self._seed_strategy_history()
                    await self.websocket_manager.restart(sorted(self.symbol_registry.data_symbols))
                    self.logger.info(
                        "symbol universe refreshed data_symbols=%s candidate_symbols=%s",
                        len(self.symbol_registry.data_symbols),
                        len(self.symbol_registry.candidate_symbols),
                    )
            except Exception as exc:
                self.logger.error("symbol refresh failed error=%s", exc)

    async def _db_flush_loop(self) -> None:
        while not self.stop_event.is_set():
            await asyncio.sleep(1)
            await self._flush_finalized_batches()

    async def _heartbeat_loop(self) -> None:
        if not self.settings.heartbeat_enabled:
            return
        interval = self.settings.heartbeat_interval_seconds
        while not self.stop_event.is_set():
            await asyncio.sleep(interval)
            if self.stop_event.is_set():
                break
            try:
                uptime_seconds = (
                    int(time.monotonic() - self._app_started_monotonic)
                    if self._app_started_monotonic is not None
                    else 0
                )
                await self.notifier.send_info(
                    "HEARTBEAT",
                    details={
                        "uptime": _format_uptime(uptime_seconds),
                        "uptime_seconds": uptime_seconds,
                        "active_positions": self.position_state.active_position_count(),
                        "strategy_interval": self.settings.strategy_interval,
                        "live_trading": self.settings.enable_live_trading,
                        "testnet": self.settings.testnet,
                        "data_symbols": len(self.symbol_registry.data_symbols),
                    },
                )
            except Exception as exc:
                self.logger.error("heartbeat send failed error=%s", exc)

    async def _flush_finalized_batches(self) -> None:
        async with self._pending_lock:
            pending = {interval: list(rows) for interval, rows in self._pending_finalized.items()}
            self._pending_finalized = {self.settings.strategy_interval: []}
        for interval, bars in pending.items():
            if not bars:
                continue
            try:
                inserted = await asyncio.to_thread(
                    self.repository.bulk_insert_klines, self.settings.strategy_table_name, bars
                )
                self._db_flush_failures[interval] = 0
                self.logger.info("db flush complete interval=%s bars=%s inserted=%s", interval, len(bars), inserted)
            except Exception as exc:
                self._db_flush_failures[interval] += 1
                async with self._pending_lock:
                    self._pending_finalized[interval] = bars + self._pending_finalized[interval]
                self.logger.error(
                    "db flush failed interval=%s bars=%s attempt=%s/3 error=%s",
                    interval,
                    len(bars),
                    self._db_flush_failures[interval],
                    exc,
                )
                await self.notifier.send_error(
                    "DB_WRITE_FAILED",
                    error_message=str(exc),
                    details={
                        "interval": interval,
                        "bars": len(bars),
                        "attempt": f"{self._db_flush_failures[interval]}/3",
                    },
                )
                if self._db_flush_failures[interval] >= 3:
                    self.logger.error("[BLOCKED] db flush exceeded retry budget interval=%s", interval)
                    await self.notifier.send_error(
                        "DB_WRITE_BLOCKED",
                        error_message=str(exc),
                        details={"interval": interval, "bars": len(bars)},
                    )
                    self.stop_event.set()

    async def _seed_strategy_history(self) -> None:
        symbols = sorted(self.symbol_registry.evaluation_symbols())
        bars = self.repository.fetch_recent_klines(
            self.settings.strategy_table_name,
            symbols,
            self.settings.kline_seed_limit,
            self.settings.strategy_interval,
        )
        await self.staging_store.seed_finalized_bars(bars)
        self.logger.info(
            "seeded rolling history interval=%s bars=%s",
            self.settings.strategy_interval,
            len(bars),
        )

    async def _send_startup_notifications(self) -> None:
        await self.notifier.send_info("APP_STARTUP_SUCCESS")
        await self.notifier.send_info(
            "MODE_SUMMARY",
            details={
                "testnet": self.settings.testnet,
                "enable_live_trading": self.settings.enable_live_trading,
                "function_test_mode": self.settings.function_test_mode,
                "function_test_symbol": self.settings.function_test_symbol,
                "position_sizing_mode": self.settings.position_sizing_mode,
                "strategy_interval": self.settings.strategy_interval,
                "strategy_table": self.settings.strategy_table_name,
                "stop_working_type": self.settings.stop_working_type,
                "max_concurrent_positions": self.settings.max_concurrent_positions,
                "target_notional_usdt": self.settings.target_notional_usdt,
            },
        )
        if not self.settings.testnet and self.settings.enable_live_trading:
            await self.notifier.send_warning(
                "LIVE_PRODUCTION_MODE",
                details={
                    "function_test_mode": self.settings.function_test_mode,
                    "function_test_symbol": self.settings.function_test_symbol,
                },
            )

    @staticmethod
    def _parse_ws_kline(payload: dict) -> Kline:
        data = payload["k"]
        interval = data["i"]
        return Kline(
            symbol=payload["s"],
            interval=interval,
            open_time=datetime.fromtimestamp(int(data["t"]) / 1000, tz=UTC),
            close_time=datetime.fromtimestamp(int(data["T"]) / 1000, tz=UTC),
            open_price=Decimal(str(data["o"])),
            high_price=Decimal(str(data["h"])),
            low_price=Decimal(str(data["l"])),
            close_price=Decimal(str(data["c"])),
            volume=Decimal(str(data["v"])),
            closed=bool(data["x"]),
            event_time=datetime.fromtimestamp(int(payload["E"]) / 1000, tz=UTC),
        )
