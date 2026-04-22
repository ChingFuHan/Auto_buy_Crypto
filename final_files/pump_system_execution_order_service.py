from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

from config import Settings
from pump_system.cache.staging_store import StagingStore
from pump_system.exchange.binance_client import BinanceClient, BinanceAPIError
from pump_system.exchange.symbol_registry import SymbolRegistry
from pump_system.execution.sizing import build_sizing_decision
from pump_system.fallback_stop.manager import FallbackStopManager
from pump_system.models import FallbackStopRecord, SignalDecision, utc_now
from pump_system.state.position_state import PositionState
from pump_system.strategy.signal_engine import SignalEngine
from pump_system.utils.decimal_utils import decimal_to_str

if TYPE_CHECKING:
    from pump_system.notify.telegram_notifier import TelegramNotifier


class OrderService:
    """Signal evaluation, pre-trade checks, entry order, and native stop placement."""

    def __init__(
        self,
        settings: Settings,
        exchange_client: BinanceClient,
        symbol_registry: SymbolRegistry,
        staging_store: StagingStore,
        position_state: PositionState,
        signal_engine: SignalEngine,
        fallback_manager: FallbackStopManager,
        notifier: "TelegramNotifier | None" = None,
    ) -> None:
        self.settings = settings
        self.exchange_client = exchange_client
        self.symbol_registry = symbol_registry
        self.staging_store = staging_store
        self.position_state = position_state
        self.signal_engine = signal_engine
        self.fallback_manager = fallback_manager
        self.notifier = notifier
        self.logger = logging.getLogger("execution.order")
        self._symbol_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last_handled_bar: dict[str, str] = {}

    async def on_market_update(self, symbol: str) -> None:
        if not self.symbol_registry.should_evaluate(symbol):
            return

        lock = self._symbol_locks[symbol]
        if lock.locked():
            return

        async with lock:
            try:
                await self._evaluate_symbol(symbol)
            except Exception as exc:
                self.logger.error("[BLOCKED] symbol evaluation failed symbol=%s error=%s", symbol, exc)
                if self.notifier is not None:
                    await self.notifier.send_error(
                        "SYMBOL_EVALUATION_BLOCKED",
                        symbol=symbol,
                        error_message=str(exc),
                    )

    async def _evaluate_symbol(self, symbol: str) -> None:
        one_m_limit = max(self.settings.strategy.one_m_lookback, self.settings.strategy.one_m_breakout_lookback, 5)
        three_m_limit = max(self.settings.strategy.three_m_lookback, self.settings.strategy.three_m_breakout_lookback, 3)
        finalized_1m, current_1m, finalized_3m, current_3m = await self.staging_store.get_signal_snapshot(
            symbol,
            one_m_limit,
            three_m_limit,
        )

        decision = self.signal_engine.evaluate(symbol, finalized_1m, current_1m, finalized_3m, current_3m)
        self.logger.info("signal check symbol=%s triggered=%s reason=%s metrics=%s", symbol, decision.triggered, decision.reason, decision.metrics)
        if not decision.triggered or current_1m is None:
            return

        bar_key = f"{symbol}:{current_1m.open_time.isoformat()}"
        if self._last_handled_bar.get(symbol) == bar_key:
            return

        if self.notifier is not None:
            await self.notifier.send_info(
                "SIGNAL_TRIGGERED",
                symbol=symbol,
                side="BUY",
                entry_price=decision.current_price,
                stop_price=decision.stop_reference_low,
                details=decision.metrics,
            )

        await self.position_state.refresh_symbol(symbol)
        if self.position_state.has_open_position(symbol):
            self.logger.info("[SKIP] existing position symbol=%s", symbol)
            if self.notifier is not None:
                await self.notifier.send_info("SKIP_EXISTING_POSITION", symbol=symbol)
            return
        if self.position_state.active_position_count() >= self.settings.max_concurrent_positions:
            self.logger.info("[SKIP] max concurrent positions reached symbol=%s", symbol)
            if self.notifier is not None:
                await self.notifier.send_warning(
                    "SKIP_MAX_CONCURRENT_POSITIONS",
                    symbol=symbol,
                    details={"max_concurrent_positions": self.settings.max_concurrent_positions},
                )
            return

        symbol_info = self.symbol_registry.get(symbol)
        if symbol_info is None:
            return
        if "STOP_MARKET" not in symbol_info.order_types or "MARKET" not in symbol_info.order_types:
            self.logger.warning("[SKIP] required order types missing symbol=%s", symbol)
            if self.notifier is not None:
                await self.notifier.send_warning("SKIP_REQUIRED_ORDER_TYPES_MISSING", symbol=symbol)
            return

        if not self.exchange_client.has_private_api:
            self.logger.warning("[BLOCKED] private API unavailable; order flow skipped symbol=%s", symbol)
            if self.notifier is not None:
                await self.notifier.send_error("PRIVATE_API_UNAVAILABLE", symbol=symbol)
            return

        try:
            account_info = await self.exchange_client.get_account_info()
            leverage_bracket = await self.exchange_client.get_leverage_bracket(symbol)
        except Exception as exc:
            if self.notifier is not None:
                await self.notifier.send_error("ACCOUNT_OR_LEVERAGE_FETCH_FAILED", symbol=symbol, error_message=str(exc))
            raise
        max_leverage = self._extract_max_leverage(leverage_bracket)
        try:
            available_balance = self._extract_available_balance(account_info)
        except Exception as exc:
            if self.notifier is not None:
                await self.notifier.send_error("AVAILABLE_BALANCE_MISSING", symbol=symbol, error_message=str(exc))
            raise
        sizing = build_sizing_decision(
            symbol_info=symbol_info,
            price=decision.current_price or current_1m.close_price,
            available_balance=available_balance,
            target_notional=self.settings.target_notional_usdt,
            max_leverage=max_leverage,
        )
        self.logger.info("quantity plan symbol=%s result=%s", symbol, sizing)

        if not sizing.can_trade:
            self.logger.info("[SKIP] no legal order size symbol=%s reason=%s", symbol, sizing.reason)
            if self.notifier is not None:
                await self.notifier.send_warning(
                    "SKIP_MIN_LEGAL_ORDER_UNREACHABLE",
                    symbol=symbol,
                    side="BUY",
                    entry_price=decision.current_price,
                    stop_price=decision.stop_reference_low,
                    error_message=sizing.reason,
                )
            return

        if self.settings.function_test_mode and self.settings.enable_live_trading and symbol != self.settings.function_test_symbol:
            self._last_handled_bar[symbol] = bar_key
            self.logger.warning("[SKIP] function test mode blocked live order symbol=%s test_symbol=%s", symbol, self.settings.function_test_symbol)
            if self.notifier is not None:
                await self.notifier.send_warning(
                    "FUNCTION_TEST_MODE_SKIPPED_LIVE_ORDER",
                    symbol=symbol,
                    side="BUY",
                    quantity=sizing.quantity,
                    entry_price=decision.current_price,
                    stop_price=decision.stop_reference_low,
                    working_type=self.settings.stop_working_type,
                    details={"function_test_symbol": self.settings.function_test_symbol},
                )
            return

        if not self.settings.enable_live_trading:
            self._last_handled_bar[symbol] = bar_key
            self.logger.warning(
                "[SKIP] live trading disabled; simulated entry symbol=%s qty=%s stop=%s leverage=%s used_max_affordable=%s",
                symbol,
                sizing.quantity,
                decision.stop_reference_low,
                sizing.leverage,
                sizing.used_max_affordable,
            )
            return

        if not await self.exchange_client.ensure_time_sync(force=True):
            self.logger.error("[BLOCKED] abort trade due to unhealthy server time symbol=%s", symbol)
            if self.notifier is not None:
                await self.notifier.send_error("SERVER_TIME_UNHEALTHY_ABORT_TRADE", symbol=symbol)
            return

        try:
            margin_result = await self.exchange_client.set_margin_type(symbol, "CROSSED")
            self.logger.info("margin type configured symbol=%s result=%s", symbol, margin_result)
        except Exception as exc:
            if self.notifier is not None:
                await self.notifier.send_error("SET_MARGIN_TYPE_FAILED", symbol=symbol, error_message=str(exc))
            return
        try:
            leverage_result = await self.exchange_client.set_leverage(symbol, sizing.leverage)
            self.logger.info("leverage configured symbol=%s leverage=%s result=%s", symbol, sizing.leverage, leverage_result)
        except Exception as exc:
            if self.notifier is not None:
                await self.notifier.send_error("SET_LEVERAGE_FAILED", symbol=symbol, error_message=str(exc))
            return

        try:
            market_order = await self.exchange_client.create_order(
                {
                    "symbol": symbol,
                    "side": "BUY",
                    "type": "MARKET",
                    "quantity": decimal_to_str(sizing.quantity),
                    "newOrderRespType": "RESULT",
                    "newClientOrderId": f"entry_{symbol.lower()}_{int(utc_now().timestamp())}",
                }
            )
        except Exception as exc:
            if self.notifier is not None:
                await self.notifier.send_error(
                    "ENTRY_ORDER_FAILED",
                    symbol=symbol,
                    side="BUY",
                    quantity=sizing.quantity,
                    entry_price=decision.current_price,
                    stop_price=decision.stop_reference_low,
                    error_message=str(exc),
                )
            return
        self.logger.info("market entry success symbol=%s result=%s", symbol, market_order)
        if self.notifier is not None:
            await self.notifier.send_trade(
                "ENTRY_ORDER_SUCCESS",
                symbol=symbol,
                side="BUY",
                quantity=sizing.quantity,
                entry_price=market_order.get("avgPrice") or decision.current_price,
                stop_price=decision.stop_reference_low,
                order_id=market_order.get("orderId"),
                details={
                    "used_max_affordable": sizing.used_max_affordable,
                    "available_balance": available_balance,
                    "requested_notional": sizing.requested_notional,
                    "final_notional": sizing.final_notional,
                    "leverage": sizing.leverage,
                },
            )

        self._last_handled_bar[symbol] = bar_key
        stop_ok = await self._place_exchange_stop(symbol, decision, market_order)
        if stop_ok:
            return

        fallback_record = FallbackStopRecord(
            symbol=symbol,
            stop_price=decision.stop_reference_low or current_1m.low_price,
            quantity=Decimal(str(market_order.get("executedQty", sizing.quantity))),
            working_type=self.settings.stop_working_type,
            active=True,
            status="ACTIVE",
            entry_price=Decimal(str(market_order.get("avgPrice", decision.current_price))),
            entry_order_id=str(market_order.get("orderId", "")),
            last_price=decision.current_price,
            retry_count=self.settings.stop_order_retry_count,
            last_error="native_stop_failed",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        await self.fallback_manager.activate(fallback_record)

    async def _place_exchange_stop(self, symbol: str, decision: SignalDecision, market_order: dict) -> bool:
        stop_price = decision.stop_reference_low
        if stop_price is None:
            self.logger.error("[BLOCKED] missing stop reference low symbol=%s", symbol)
            return False

        params = {
            "symbol": symbol,
            "side": "SELL",
            "type": "STOP_MARKET",
            "stopPrice": decimal_to_str(stop_price),
            "workingType": self.settings.stop_working_type,
            "closePosition": "true",
            "priceProtect": "FALSE",
            "newClientOrderId": f"stop_{symbol.lower()}_{market_order.get('orderId', 'na')}",
        }
        self.logger.info("native stop source symbol=%s stop_low=%s working_type=%s", symbol, stop_price, self.settings.stop_working_type)

        for attempt in range(1, self.settings.stop_order_retry_count + 1):
            try:
                result = await self.exchange_client.create_order(params)
                self.logger.info("native stop success symbol=%s attempt=%s result=%s", symbol, attempt, result)
                if self.notifier is not None:
                    await self.notifier.send_trade(
                        "STOP_ORDER_SUCCESS",
                        symbol=symbol,
                        side="SELL",
                        stop_price=stop_price,
                        working_type=self.settings.stop_working_type,
                        order_id=result.get("orderId"),
                        details={"attempt": attempt},
                    )
                return True
            except Exception as exc:
                self.logger.error("native stop retry symbol=%s attempt=%s error=%s", symbol, attempt, exc)
                if self.notifier is not None:
                    await self.notifier.send_error(
                        "STOP_ORDER_RETRY",
                        symbol=symbol,
                        side="SELL",
                        stop_price=stop_price,
                        working_type=self.settings.stop_working_type,
                        order_id=market_order.get("orderId"),
                        error_message=str(exc),
                        details={"attempt": f"{attempt}/{self.settings.stop_order_retry_count}"},
                    )
        if self.notifier is not None:
            await self.notifier.send_error(
                "STOP_ORDER_FAILED",
                symbol=symbol,
                side="SELL",
                stop_price=stop_price,
                working_type=self.settings.stop_working_type,
                order_id=market_order.get("orderId"),
                error_message="native_stop_failed_after_retries",
            )
        return False

    @staticmethod
    def _extract_available_balance(account_info: dict) -> Decimal:
        if "availableBalance" in account_info:
            return Decimal(str(account_info["availableBalance"]))
        for asset in account_info.get("assets", []):
            if asset.get("asset") == "USDT" and "availableBalance" in asset:
                return Decimal(str(asset["availableBalance"]))
        raise BinanceAPIError("availableBalance_missing")

    @staticmethod
    def _extract_max_leverage(leverage_bracket: dict) -> int:
        brackets = leverage_bracket.get("brackets", [])
        if not brackets:
            raise BinanceAPIError("leverage_bracket_missing")
        return max(int(bracket["initialLeverage"]) for bracket in brackets)
