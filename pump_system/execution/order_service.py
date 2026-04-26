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
from pump_system.models import FallbackStopRecord, Kline, NativeStopTracker, SignalDecision, utc_now
from pump_system.state.position_state import PositionState
from pump_system.strategy.signal_engine import SignalEngine
from pump_system.utils.decimal_utils import decimal_to_str, floor_to_step

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
        self._active_native_stops: dict[str, NativeStopTracker] = {}

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

    async def restore_native_stop_watchlist(self) -> None:
        if not self.exchange_client.has_private_api:
            return

        for symbol, snapshot in self.position_state.positions.items():
            if snapshot.quantity <= Decimal("0"):
                continue
            algo_orders = await self.exchange_client.get_open_algo_orders(symbol=symbol, algo_type="CONDITIONAL")
            for order in algo_orders:
                client_order_id = str(order.get("clientAlgoId", ""))
                if order.get("orderType") != "STOP_MARKET":
                    continue
                if order.get("positionSide") != "LONG":
                    continue
                if not client_order_id.startswith("stop_"):
                    continue
                self._active_native_stops[symbol] = NativeStopTracker(
                    symbol=symbol,
                    client_order_id=client_order_id,
                    algo_id=str(order.get("algoId", "")),
                    stop_price=Decimal(str(order.get("triggerPrice", "0"))),
                    quantity=snapshot.quantity,
                    working_type=str(order.get("workingType", self.settings.stop_working_type)),
                    entry_price=snapshot.entry_price,
                )
                break

    async def run_native_stop_monitor(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await asyncio.sleep(self.settings.fallback_poll_interval_seconds)
            try:
                await self.reconcile_native_stops()
            except Exception as exc:
                self.logger.error("native stop monitor failed error=%s", exc)

    async def reconcile_native_stops(self) -> None:
        if not self._active_native_stops or not self.exchange_client.has_private_api:
            return

        for symbol, tracker in list(self._active_native_stops.items()):
            quantity = await self._get_current_long_quantity(symbol)
            algo_orders = await self.exchange_client.get_open_algo_orders(symbol=symbol, algo_type="CONDITIONAL")
            matching_order = next(
                (order for order in algo_orders if str(order.get("clientAlgoId", "")) == tracker.client_order_id),
                None,
            )

            if quantity > Decimal("0") and matching_order is not None:
                continue

            if quantity > Decimal("0") and matching_order is None:
                if tracker.missing_reported:
                    continue
                tracker.missing_reported = True
                self.logger.error("[BLOCKED] native stop missing on exchange symbol=%s client_order_id=%s", symbol, tracker.client_order_id)
                if self.notifier is not None:
                    await self.notifier.send_error(
                        "STOP_ORDER_MISSING",
                        symbol=symbol,
                        side="SELL",
                        quantity=tracker.quantity,
                        entry_price=tracker.entry_price,
                        stop_price=tracker.stop_price,
                        working_type=tracker.working_type,
                        order_id=tracker.algo_id,
                        error_message="native_stop_missing_on_exchange",
                        details={"client_order_id": tracker.client_order_id},
                    )
                continue

            closed_order = await self._find_order_by_client_id(symbol, tracker.client_order_id)
            self._active_native_stops.pop(symbol, None)

            if closed_order is not None and closed_order.get("status") == "FILLED":
                self.logger.info(
                    "native stop filled symbol=%s order_id=%s client_order_id=%s",
                    symbol,
                    closed_order.get("orderId"),
                    tracker.client_order_id,
                )
                if self.notifier is not None:
                    await self.notifier.send_trade(
                        "STOP_ORDER_TRIGGERED",
                        symbol=symbol,
                        side="SELL",
                        quantity=closed_order.get("executedQty") or tracker.quantity,
                        entry_price=tracker.entry_price,
                        stop_price=tracker.stop_price,
                        working_type=tracker.working_type,
                        order_id=closed_order.get("orderId"),
                        details={
                            "client_order_id": tracker.client_order_id,
                            "fill_price": closed_order.get("avgPrice", ""),
                        },
                    )
                continue

            self.logger.warning(
                "position closed without native stop fill confirmation symbol=%s client_order_id=%s",
                symbol,
                tracker.client_order_id,
            )
            if self.notifier is not None:
                await self.notifier.send_warning(
                    "STOP_ORDER_POSITION_CLOSED",
                    symbol=symbol,
                    side="SELL",
                    quantity=tracker.quantity,
                    entry_price=tracker.entry_price,
                    stop_price=tracker.stop_price,
                    working_type=tracker.working_type,
                    order_id=tracker.algo_id,
                    details={"client_order_id": tracker.client_order_id},
                )

    async def execute_manual_function_test(self) -> None:
        """Submit a real or simulated test entry for FUNCTION_TEST_SYMBOL using live exchange state."""
        symbol = self.settings.function_test_symbol
        
        await self.position_state.refresh_symbol(symbol)
        existing_qty = self.position_state.get_quantity(symbol)
        if existing_qty > Decimal("0"):
            msg = f"position already exists symbol={symbol} qty={existing_qty}, skipping entry"
            self.logger.warning("[SKIP] %s", msg)
            if self.notifier is not None:
                await self.notifier.send_warning("MANUAL_FUNCTION_TEST_SKIPPED", symbol=symbol, reason="position_already_exists", quantity=str(existing_qty))
            return
        
        if self.notifier is not None:
            await self.notifier.send_warning(
                "MANUAL_FUNCTION_TEST_STARTED",
                symbol=symbol,
                side="BUY",
                details={
                    "testnet": self.settings.testnet,
                    "enable_live_trading": self.settings.enable_live_trading,
                    "function_test_mode": self.settings.function_test_mode,
                },
            )

        symbol_info = self.symbol_registry.get(symbol)
        if symbol_info is None:
            if self.notifier is not None:
                await self.notifier.send_error("MANUAL_FUNCTION_TEST_SYMBOL_MISSING", symbol=symbol)
            raise BinanceAPIError(f"function_test_symbol_missing {symbol}")

        klines_3m = await self.exchange_client.get_klines(symbol, "3m", limit=1)
        if len(klines_3m) < 1:
            raise BinanceAPIError(f"insufficient_klines symbol={symbol}")
        latest_3m = klines_3m[-1]
        current_3m = Kline(
            symbol=symbol,
            interval="3m",
            open_time=utc_now(),
            close_time=utc_now(),
            open_price=Decimal(str(latest_3m[1])),
            high_price=Decimal(str(latest_3m[2])),
            low_price=Decimal(str(latest_3m[3])),
            close_price=Decimal(str(latest_3m[4])),
            volume=Decimal(str(latest_3m[5])),
            closed=False,
            event_time=utc_now(),
        )
        decision = SignalDecision(
            symbol=symbol,
            triggered=True,
            reason="manual_function_test",
            metrics={"mode": "manual_function_test"},
            stop_reference_low=current_3m.low_price,
            current_price=current_3m.close_price,
        )
        bar_key = f"manual:{symbol}:{int(utc_now().timestamp())}"
        await self._execute_trade(symbol, decision, current_3m, symbol_info, bar_key)

    async def _evaluate_symbol(self, symbol: str) -> None:
        three_m_limit = max(self.settings.strategy.three_m_lookback, self.settings.strategy.three_m_breakout_lookback, 5)
        finalized_3m, current_3m = await self.staging_store.get_signal_snapshot(symbol, three_m_limit)

        decision = self.signal_engine.evaluate(symbol, finalized_3m, current_3m)
        self.logger.info("signal check symbol=%s triggered=%s reason=%s metrics=%s", symbol, decision.triggered, decision.reason, decision.metrics)
        if not decision.triggered or current_3m is None:
            return

        bar_key = f"{symbol}:{current_3m.open_time.isoformat()}"
        if self._last_handled_bar.get(symbol) == bar_key:
            return

        if self.notifier is not None:
            signal_details = dict(decision.metrics)
            signal_details["stop_price_mode"] = self.settings.stop_price_mode
            await self.notifier.send_info(
                "SIGNAL_TRIGGERED",
                symbol=symbol,
                side="BUY",
                entry_price=decision.current_price,
                stop_price=decision.stop_reference_low,
                details=signal_details,
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
        await self._execute_trade(symbol, decision, current_3m, symbol_info, bar_key)

    async def _execute_trade(
        self,
        symbol: str,
        decision: SignalDecision,
        current_bar: Kline,
        symbol_info,
        bar_key: str,
    ) -> None:
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
        target_notional = self._resolve_target_notional(available_balance, max_leverage)
        self.logger.info(
            "target notional resolved symbol=%s mode=%s target_notional=%s available_balance=%s max_leverage=%s active_positions=%s max_positions=%s",
            symbol,
            self.settings.position_sizing_mode,
            target_notional,
            available_balance,
            max_leverage,
            self.position_state.active_position_count(),
            self.settings.max_concurrent_positions,
        )
        sizing = build_sizing_decision(
            symbol_info=symbol_info,
            price=decision.current_price or current_bar.close_price,
            available_balance=available_balance,
            target_notional=target_notional,
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
            estimated_stop_price = self._resolve_stop_price(
                symbol_info,
                decision,
                {"avgPrice": decimal_to_str(decision.current_price or current_bar.close_price), "executedQty": decimal_to_str(sizing.quantity)},
            )
            self.logger.warning("[SKIP] function test mode blocked live order symbol=%s test_symbol=%s", symbol, self.settings.function_test_symbol)
            if self.notifier is not None:
                await self.notifier.send_warning(
                    "FUNCTION_TEST_MODE_SKIPPED_LIVE_ORDER",
                    symbol=symbol,
                    side="BUY",
                    quantity=sizing.quantity,
                    entry_price=decision.current_price,
                    stop_price=estimated_stop_price or decision.stop_reference_low,
                    working_type=self.settings.stop_working_type,
                    details={
                        "function_test_symbol": self.settings.function_test_symbol,
                        "position_sizing_mode": self.settings.position_sizing_mode,
                        "stop_price_mode": self.settings.stop_price_mode,
                    },
                )
            return

        if not self.settings.enable_live_trading:
            self._last_handled_bar[symbol] = bar_key
            estimated_stop_price = self._resolve_stop_price(
                symbol_info,
                decision,
                {"avgPrice": decimal_to_str(decision.current_price or current_bar.close_price), "executedQty": decimal_to_str(sizing.quantity)},
            )
            self.logger.warning(
                "[SKIP] live trading disabled; simulated entry symbol=%s qty=%s stop=%s stop_price_mode=%s leverage=%s used_max_affordable=%s",
                symbol,
                sizing.quantity,
                estimated_stop_price or decision.stop_reference_low,
                self.settings.stop_price_mode,
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
                    "positionSide": "LONG",
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
        entry_price = self._resolve_entry_price(decision, market_order)
        stop_price = self._resolve_stop_price(symbol_info, decision, market_order)
        if stop_price is None:
            raw_fallback_stop = decision.stop_reference_low or current_bar.low_price
            stop_price = floor_to_step(raw_fallback_stop, symbol_info.tick_size)
            self.logger.error(
                "[RISK] configured stop price unavailable; falling back to in-progress 3m low symbol=%s fallback_stop=%s stop_price_mode=%s",
                symbol,
                stop_price,
                self.settings.stop_price_mode,
            )
        if self.notifier is not None:
            await self.notifier.send_trade(
                "ENTRY_ORDER_SUCCESS",
                symbol=symbol,
                side="BUY",
                quantity=sizing.quantity,
                entry_price=entry_price if entry_price > Decimal("0") else decision.current_price,
                stop_price=stop_price,
                order_id=market_order.get("orderId"),
                details={
                    "used_max_affordable": sizing.used_max_affordable,
                    "available_balance": available_balance,
                    "requested_notional": sizing.requested_notional,
                    "final_notional": sizing.final_notional,
                    "leverage": sizing.leverage,
                    "position_sizing_mode": self.settings.position_sizing_mode,
                    "stop_price_mode": self.settings.stop_price_mode,
                },
            )

        self._last_handled_bar[symbol] = bar_key
        stop_ok = await self._place_exchange_stop(symbol, decision, market_order, stop_price)
        if stop_ok:
            return

        fallback_record = FallbackStopRecord(
            symbol=symbol,
            stop_price=stop_price,
            quantity=Decimal(str(market_order.get("executedQty", sizing.quantity))),
            working_type=self.settings.stop_working_type,
            active=True,
            status="ACTIVE",
            entry_price=entry_price,
            entry_order_id=str(market_order.get("orderId", "")),
            last_price=decision.current_price,
            retry_count=self.settings.stop_order_retry_count,
            last_error="native_stop_failed",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        await self.fallback_manager.activate(fallback_record)

    async def _place_exchange_stop(
        self,
        symbol: str,
        decision: SignalDecision,
        market_order: dict,
        stop_price: Decimal | None = None,
    ) -> bool:
        stop_price = stop_price if stop_price is not None else decision.stop_reference_low
        if stop_price is None:
            self.logger.error("[BLOCKED] missing stop price symbol=%s stop_price_mode=%s", symbol, self.settings.stop_price_mode)
            return False

        client_order_id = f"stop_{symbol.lower()}_{int(utc_now().timestamp())}"
        try:
            stop_order = await self.exchange_client.create_algo_order(
                {
                    "algoType": "CONDITIONAL",
                    "symbol": symbol,
                    "side": "SELL",
                    "positionSide": "LONG",
                    "type": "STOP_MARKET",
                    "triggerPrice": decimal_to_str(stop_price),
                    "workingType": self.settings.stop_working_type,
                    "closePosition": "true",
                    "clientAlgoId": client_order_id,
                }
            )
            quantity = Decimal(str(market_order.get("executedQty") or market_order.get("origQty") or "0"))
            entry_price = self._resolve_entry_price(decision, market_order)
            tracker = NativeStopTracker(
                symbol=symbol,
                client_order_id=client_order_id,
                algo_id=str(stop_order.get("algoId", "")),
                stop_price=stop_price,
                quantity=quantity,
                working_type=self.settings.stop_working_type,
                entry_price=entry_price,
            )
            self._active_native_stops[symbol] = tracker
            self.logger.info(
                "native stop algo order placed symbol=%s trigger_price=%s algo_id=%s",
                symbol,
                stop_price,
                stop_order.get("algoId"),
            )
            if self.notifier is not None:
                await self.notifier.send_trade(
                    "STOP_ORDER_SUCCESS",
                    symbol=symbol,
                    side="SELL",
                    quantity=quantity,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    working_type=self.settings.stop_working_type,
                    order_id=stop_order.get("algoId"),
                    details={
                        "client_order_id": client_order_id,
                        "stop_price_mode": self.settings.stop_price_mode,
                    },
                )
            return True
        except Exception as exc:
            self.logger.error("native stop order failed symbol=%s stop_price=%s error=%s", symbol, stop_price, exc)
            return False

    @staticmethod
    def _resolve_entry_price(decision: SignalDecision, market_order: dict) -> Decimal:
        entry_price = Decimal(str(market_order.get("avgPrice") or "0"))
        if entry_price <= Decimal("0") and decision.current_price is not None:
            return decision.current_price
        return entry_price

    def _resolve_target_notional(self, available_balance: Decimal, max_leverage: int) -> Decimal:
        if self.settings.position_sizing_mode == "FIXED_NOTIONAL":
            return self.settings.target_notional_usdt
        if self.settings.position_sizing_mode == "BALANCE_SPLIT":
            active_positions = self.position_state.active_position_count()
            remaining_slots = max(self.settings.max_concurrent_positions - active_positions, 1)
            return (available_balance * Decimal(max_leverage)) / Decimal(remaining_slots)
        self.logger.error("[BLOCKED] unsupported position sizing mode mode=%s", self.settings.position_sizing_mode)
        return self.settings.target_notional_usdt

    def _resolve_stop_price(self, symbol_info, decision: SignalDecision, market_order: dict) -> Decimal | None:
        if self.settings.stop_price_mode == "IN_PROGRESS_3M_LOW":
            raw_stop = decision.stop_reference_low
        elif self.settings.stop_price_mode == "NOTIONAL_RISK_PCT":
            entry_price = self._resolve_entry_price(decision, market_order)
            if entry_price <= Decimal("0"):
                return None
            raw_stop = entry_price * (Decimal("1") - self.settings.stop_notional_risk_pct)
        else:
            self.logger.error("[BLOCKED] unsupported stop price mode mode=%s", self.settings.stop_price_mode)
            return None

        if raw_stop is None or raw_stop <= Decimal("0"):
            return None
        stop_price = floor_to_step(raw_stop, symbol_info.tick_size)
        return stop_price if stop_price > Decimal("0") else None

    async def _get_current_long_quantity(self, symbol: str) -> Decimal:
        payload = await self.exchange_client.get_position_risk(symbol)
        for item in payload:
            if item.get("symbol") != symbol:
                continue
            if item.get("positionSide") != "LONG":
                continue
            quantity = Decimal(str(item.get("positionAmt", "0")))
            if quantity > Decimal("0"):
                return quantity.copy_abs()
        return Decimal("0")

    async def _find_order_by_client_id(self, symbol: str, client_order_id: str) -> dict | None:
        orders = await self.exchange_client.get_all_orders(symbol, limit=20)
        for order in reversed(orders):
            if str(order.get("clientOrderId", "")) == client_order_id:
                return dict(order)
        return None

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
