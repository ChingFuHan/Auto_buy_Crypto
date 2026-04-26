from __future__ import annotations

from decimal import Decimal

from config import StrategyConfig
from pump_system.models import Kline, SignalDecision


class SignalEngine:
    """Turn the first-pump concept into deterministic 3m-only entry rules."""

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    def evaluate(
        self,
        symbol: str,
        finalized_3m: list[Kline],
        current_3m: Kline | None,
    ) -> SignalDecision:
        if current_3m is None:
            return SignalDecision(symbol=symbol, triggered=False, reason="missing_in_progress_3m")

        required_3m = max(self.config.three_m_lookback, self.config.three_m_breakout_lookback, 5)
        if len(finalized_3m) < required_3m:
            return SignalDecision(symbol=symbol, triggered=False, reason="insufficient_history")

        metrics: dict[str, str] = {}
        reasons: list[str] = []

        three_m_window = finalized_3m[-self.config.three_m_lookback :]
        breakout_3m_window = finalized_3m[-self.config.three_m_breakout_lookback :]

        atr_3m = self._avg_range_pct(three_m_window)
        range_3m = self._window_range_pct(three_m_window)
        vol_ratio_3m = self._volume_ratio(current_3m, three_m_window)
        ret_3m = self._bar_return_pct(current_3m, finalized_3m[-1].close_price)
        breakout_3m = current_3m.high_price > max(bar.high_price for bar in breakout_3m_window)
        prior_runup = self._window_range_pct(finalized_3m[-5:])
        recent_green_bars = self._recent_green_bars(finalized_3m)

        metrics["mode"] = "3m_only"
        metrics["atr_3m_pct"] = format(atr_3m, "f")
        metrics["range_3m_pct"] = format(range_3m, "f")
        metrics["vol_ratio_3m"] = format(vol_ratio_3m, "f")
        metrics["ret_3m_pct"] = format(ret_3m, "f")
        metrics["prior_runup_3m_pct"] = format(prior_runup, "f")
        metrics["recent_green_3m_bars"] = str(recent_green_bars)
        metrics["breakout_3m"] = str(breakout_3m)
        metrics["stop_source"] = "in_progress_3m_low"

        if atr_3m > self.config.three_m_atr_pct_max or range_3m > self.config.three_m_range_pct_max:
            reasons.append("3m_not_compressed")
        if vol_ratio_3m < self.config.three_m_volume_multiple:
            reasons.append("3m_volume_too_low")
        if ret_3m < self.config.three_m_return_pct_min:
            reasons.append("3m_push_too_small")
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
            stop_reference_low=current_3m.low_price,
            current_price=current_3m.close_price,
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
