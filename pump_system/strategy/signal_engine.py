from __future__ import annotations

from decimal import Decimal

from config import StrategyConfig
from pump_system.models import Kline, SignalDecision


class SignalEngine:
    """Turn the first-pump concept into deterministic 1m + 3m entry rules."""

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    def evaluate(
        self,
        symbol: str,
        finalized_1m: list[Kline],
        current_1m: Kline | None,
        finalized_3m: list[Kline],
        current_3m: Kline | None,
    ) -> SignalDecision:
        if current_1m is None or current_3m is None:
            return SignalDecision(symbol=symbol, triggered=False, reason="missing_in_progress_bars")

        required_1m = max(self.config.one_m_lookback, self.config.one_m_breakout_lookback, 5)
        required_3m = max(self.config.three_m_lookback, self.config.three_m_breakout_lookback, 3)
        if len(finalized_1m) < required_1m or len(finalized_3m) < required_3m:
            return SignalDecision(symbol=symbol, triggered=False, reason="insufficient_history")

        metrics: dict[str, str] = {}
        reasons: list[str] = []

        one_m_window = finalized_1m[-self.config.one_m_lookback :]
        three_m_window = finalized_3m[-self.config.three_m_lookback :]
        breakout_1m_window = finalized_1m[-self.config.one_m_breakout_lookback :]
        breakout_3m_window = finalized_3m[-self.config.three_m_breakout_lookback :]

        atr_1m = self._avg_range_pct(one_m_window)
        atr_3m = self._avg_range_pct(three_m_window)
        range_1m = self._window_range_pct(one_m_window)
        range_3m = self._window_range_pct(three_m_window)
        vol_ratio_1m = self._volume_ratio(current_1m, one_m_window)
        vol_ratio_3m = self._volume_ratio(current_3m, three_m_window)
        ret_1m = self._bar_return_pct(current_1m, finalized_1m[-1].close_price)
        ret_3m = self._bar_return_pct(current_3m, finalized_3m[-1].close_price)
        breakout_1m = current_1m.high_price > max(bar.high_price for bar in breakout_1m_window)
        breakout_3m = current_3m.high_price > max(bar.high_price for bar in breakout_3m_window)
        prior_runup = self._window_range_pct(finalized_1m[-5:])
        recent_green_bars = self._recent_green_bars(finalized_1m)

        metrics["atr_1m_pct"] = format(atr_1m, "f")
        metrics["atr_3m_pct"] = format(atr_3m, "f")
        metrics["range_1m_pct"] = format(range_1m, "f")
        metrics["range_3m_pct"] = format(range_3m, "f")
        metrics["vol_ratio_1m"] = format(vol_ratio_1m, "f")
        metrics["vol_ratio_3m"] = format(vol_ratio_3m, "f")
        metrics["ret_1m_pct"] = format(ret_1m, "f")
        metrics["ret_3m_pct"] = format(ret_3m, "f")
        metrics["prior_runup_pct"] = format(prior_runup, "f")
        metrics["recent_green_bars"] = str(recent_green_bars)
        metrics["breakout_1m"] = str(breakout_1m)
        metrics["breakout_3m"] = str(breakout_3m)

        if atr_1m > self.config.one_m_atr_pct_max or range_1m > self.config.one_m_range_pct_max:
            reasons.append("1m_not_compressed")
        if atr_3m > self.config.three_m_atr_pct_max or range_3m > self.config.three_m_range_pct_max:
            reasons.append("3m_not_compressed")
        if vol_ratio_1m < self.config.one_m_volume_multiple:
            reasons.append("1m_volume_too_low")
        if vol_ratio_3m < self.config.three_m_volume_multiple:
            reasons.append("3m_volume_too_low")
        if ret_1m < self.config.one_m_return_pct_min:
            reasons.append("1m_push_too_small")
        if ret_3m < self.config.three_m_return_pct_min:
            reasons.append("3m_push_too_small")
        if not breakout_1m:
            reasons.append("1m_not_breakout")
        if not breakout_3m:
            reasons.append("3m_not_breakout")
        if prior_runup > self.config.prior_runup_limit_pct:
            reasons.append("already_extended")
        if ret_3m > self.config.three_m_overheat_limit_pct:
            reasons.append("3m_overheated")
        if recent_green_bars > self.config.max_recent_green_bars:
            reasons.append("recent_green_stretch")

        triggered = not reasons
        return SignalDecision(
            symbol=symbol,
            triggered=triggered,
            reason="triggered" if triggered else ",".join(reasons),
            metrics=metrics,
            stop_reference_low=current_1m.low_price,
            current_price=current_1m.close_price,
        )

    @staticmethod
    def _avg_range_pct(bars: list[Kline]) -> Decimal:
        total = sum((bar.high_price - bar.low_price) / bar.close_price for bar in bars if bar.close_price > 0)
        return total / Decimal(len(bars))

    @staticmethod
    def _window_range_pct(bars: list[Kline]) -> Decimal:
        low = min(bar.low_price for bar in bars)
        high = max(bar.high_price for bar in bars)
        if low <= Decimal("0"):
            return Decimal("0")
        return (high - low) / low

    @staticmethod
    def _volume_ratio(current_bar: Kline, history: list[Kline]) -> Decimal:
        average = sum(bar.volume for bar in history) / Decimal(len(history))
        if average <= Decimal("0"):
            return Decimal("0")
        return current_bar.volume / average

    @staticmethod
    def _bar_return_pct(current_bar: Kline, reference_close: Decimal) -> Decimal:
        if reference_close <= Decimal("0"):
            return Decimal("0")
        return (current_bar.close_price - reference_close) / reference_close

    @staticmethod
    def _recent_green_bars(bars: list[Kline]) -> int:
        count = 0
        for bar in reversed(bars):
            if bar.close_price > bar.open_price:
                count += 1
                continue
            break
        return count
