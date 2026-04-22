from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from config import Settings
from pump_system.cache.staging_store import StagingStore
from pump_system.exchange.binance_client import BinanceClient
from pump_system.models import FallbackStopRecord, utc_now
from pump_system.state.csv_state import AtomicCsvState
from pump_system.state.position_state import PositionState
from pump_system.utils.decimal_utils import decimal_to_str

if TYPE_CHECKING:
    from pump_system.notify.telegram_notifier import TelegramNotifier


class FallbackStopManager:
    """Local CSV-backed stop monitor when exchange STOP_MARKET placement fails."""

    FIELDNAMES = [
        "symbol",
        "stop_price",
        "quantity",
        "working_type",
        "active",
        "status",
        "entry_price",
        "entry_order_id",
        "last_price",
        "retry_count",
        "last_error",
        "created_at",
        "updated_at",
    ]

    def __init__(
        self,
        settings: Settings,
        exchange_client: BinanceClient,
        position_state: PositionState,
        staging_store: StagingStore,
        notifier: "TelegramNotifier | None" = None,
    ) -> None:
        self.settings = settings
        self.exchange_client = exchange_client
        self.position_state = position_state
        self.staging_store = staging_store
        self.notifier = notifier
        self.logger = logging.getLogger("fallback.stop")
        self.csv_state = AtomicCsvState(settings.fallback_csv_path, self.FIELDNAMES)
        self.records: dict[str, FallbackStopRecord] = {}

    async def load_existing(self) -> None:
        rows = await self.csv_state.load_rows()
        restored = {
            record.symbol: record
            for record in (FallbackStopRecord.from_row(row) for row in rows)
            if record.active
        }
        if not restored or not self.exchange_client.has_private_api:
            self.records = restored
            self.logger.info("restored fallback stops active=%s", len(self.records))
            return

        await self.position_state.refresh()
        active_records: dict[str, FallbackStopRecord] = {}
        for symbol, record in restored.items():
            if self.position_state.get_quantity(symbol) > Decimal("0"):
                active_records[symbol] = record
                continue
            record.active = False
            record.status = "POSITION_ALREADY_CLOSED"
            record.updated_at = utc_now()
            await self.csv_state.upsert_row("symbol", record.to_row())
            self.logger.info("fallback stop removed on restore symbol=%s reason=no_position", symbol)
        self.records = active_records
        self.logger.info("restored fallback stops active=%s", len(self.records))

    async def activate(self, record: FallbackStopRecord) -> None:
        self.records[record.symbol] = record
        await self.csv_state.upsert_row("symbol", record.to_row())
        self.logger.error("fallback stop activated symbol=%s stop_price=%s", record.symbol, record.stop_price)
        if self.notifier is not None:
            await self.notifier.send_error(
                "FALLBACK_STOP_ACTIVATED",
                symbol=record.symbol,
                side="SELL",
                quantity=record.quantity,
                entry_price=record.entry_price,
                stop_price=record.stop_price,
                working_type=record.working_type,
                order_id=record.entry_order_id,
                error_message=record.last_error,
            )

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await asyncio.sleep(self.settings.fallback_poll_interval_seconds)
            await self._poll_active_stops()

    async def _poll_active_stops(self) -> None:
        for symbol, record in list(self.records.items()):
            if not record.active:
                continue
            current_price = await self._current_price(record)
            if current_price is None:
                continue
            if current_price > record.stop_price:
                continue
            await self._trigger_close(record, current_price)

    async def _current_price(self, record: FallbackStopRecord) -> Decimal | None:
        if record.working_type == "MARK_PRICE":
            try:
                return await self.exchange_client.get_mark_price(record.symbol)
            except Exception as exc:
                self.logger.warning("mark price fetch failed symbol=%s error=%s", record.symbol, exc)
                return None

        source, price = await self.staging_store.contract_trigger_price(record.symbol)
        if price is not None:
            self.logger.info("fallback trigger source symbol=%s source=%s price=%s", record.symbol, source, price)
        return price

    async def _trigger_close(self, record: FallbackStopRecord, current_price: Decimal) -> None:
        record.last_price = current_price
        record.updated_at = utc_now()

        if not self.settings.enable_live_trading:
            record.active = False
            record.status = "SIMULATED_TRIGGERED"
            await self.csv_state.upsert_row("symbol", record.to_row())
            self.records.pop(record.symbol, None)
            self.logger.warning("[SKIP] live trading disabled; fallback close simulated symbol=%s", record.symbol)
            if self.notifier is not None:
                await self.notifier.send_warning(
                    "FALLBACK_STOP_SIMULATED_TRIGGER",
                    symbol=record.symbol,
                    side="SELL",
                    quantity=record.quantity,
                    entry_price=record.entry_price,
                    stop_price=record.stop_price,
                    working_type=record.working_type,
                )
            return

        await self.position_state.refresh_symbol(record.symbol)
        quantity = self.position_state.get_quantity(record.symbol)
        if quantity <= Decimal("0"):
            record.active = False
            record.status = "POSITION_ALREADY_CLOSED"
            await self.csv_state.upsert_row("symbol", record.to_row())
            self.records.pop(record.symbol, None)
            self.logger.info("fallback stop removed symbol=%s reason=no_position", record.symbol)
            if self.notifier is not None:
                await self.notifier.send_info(
                    "FALLBACK_STOP_POSITION_ALREADY_CLOSED",
                    symbol=record.symbol,
                    stop_price=record.stop_price,
                    order_id=record.entry_order_id,
                )
            return

        if self.notifier is not None:
            await self.notifier.send_warning(
                "FALLBACK_STOP_TRIGGERED",
                symbol=record.symbol,
                side="SELL",
                quantity=quantity,
                entry_price=record.entry_price,
                stop_price=record.stop_price,
                working_type=record.working_type,
                order_id=record.entry_order_id,
                details={"trigger_price": current_price},
            )

        for attempt in range(1, self.settings.stop_order_retry_count + 1):
            try:
                await self.exchange_client.create_order(
                    {
                        "symbol": record.symbol,
                        "side": "SELL",
                        "positionSide": "LONG",
                        "type": "MARKET",
                        "quantity": decimal_to_str(quantity),
                        "newClientOrderId": f"fallback_{record.symbol.lower()}_{attempt}",
                    }
                )
                record.active = False
                record.status = "CLOSED"
                record.retry_count = attempt
                record.last_error = ""
                await self.csv_state.upsert_row("symbol", record.to_row())
                self.records.pop(record.symbol, None)
                self.logger.error("fallback close success symbol=%s attempt=%s", record.symbol, attempt)
                if self.notifier is not None:
                    await self.notifier.send_trade(
                        "FALLBACK_CLOSE_SUCCESS",
                        symbol=record.symbol,
                        side="SELL",
                        quantity=quantity,
                        entry_price=record.entry_price,
                        stop_price=record.stop_price,
                        working_type=record.working_type,
                        order_id=record.entry_order_id,
                        details={"attempt": attempt, "trigger_price": current_price},
                    )
                return
            except Exception as exc:
                record.retry_count = attempt
                record.last_error = str(exc)
                self.logger.error("fallback close retry symbol=%s attempt=%s error=%s", record.symbol, attempt, exc)
                if self.notifier is not None:
                    await self.notifier.send_error(
                        "FALLBACK_CLOSE_RETRY",
                        symbol=record.symbol,
                        side="SELL",
                        quantity=quantity,
                        entry_price=record.entry_price,
                        stop_price=record.stop_price,
                        working_type=record.working_type,
                        order_id=record.entry_order_id,
                        error_message=str(exc),
                        details={"attempt": f"{attempt}/{self.settings.stop_order_retry_count}", "trigger_price": current_price},
                    )

        record.active = False
        record.status = "BLOCKED"
        await self.csv_state.upsert_row("symbol", record.to_row())
        self.records.pop(record.symbol, None)
        self.logger.error("[BLOCKED] fallback close failed symbol=%s error=%s", record.symbol, record.last_error)
        if self.notifier is not None:
            await self.notifier.send_error(
                "FALLBACK_CLOSE_BLOCKED",
                symbol=record.symbol,
                side="SELL",
                quantity=quantity,
                entry_price=record.entry_price,
                stop_price=record.stop_price,
                working_type=record.working_type,
                order_id=record.entry_order_id,
                error_message=record.last_error,
                details={"trigger_price": current_price},
            )
