from __future__ import annotations

from decimal import Decimal

from config import StrategyConfig
from pump_system.models import Kline, SignalDecision


class SignalEngine:
    """Turn the first-pump concept into deterministic configured-interval entry rules."""

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    def evaluate(
        self,
        symbol: str,
        finalized_bars: list[Kline],
        current_bar: Kline | None,
    ) -> SignalDecision:
        interval = self.config.interval
        if current_bar is None:
            return SignalDecision(symbol=symbol, triggered=False, reason=f"missing_in_progress_{interval}")

        required_bars = max(self.config.lookback, self.config.breakout_lookback, 5)
        if len(finalized_bars) < required_bars:
            return SignalDecision(symbol=symbol, triggered=False, reason="insufficient_history")

        metrics: dict[str, str] = {}
        reasons: list[str] = []

        interval_window = finalized_bars[-self.config.lookback :]
        breakout_window = finalized_bars[-self.config.breakout_lookback :]

        atr = self._avg_range_pct(interval_window)
        window_range = self._window_range_pct(interval_window)
        vol_ratio = self._volume_ratio(current_bar, interval_window)
        bar_return = self._bar_return_pct(current_bar, finalized_bars[-1].close_price)
        breakout = current_bar.high_price > max(bar.high_price for bar in breakout_window)
        prior_runup = self._window_range_pct(finalized_bars[-5:])
        recent_green_bars = self._recent_green_bars(finalized_bars)

        metrics["mode"] = f"{interval}_only"
        metrics[f"atr_{interval}_pct"] = format(atr, "f")
        metrics[f"range_{interval}_pct"] = format(window_range, "f")
        metrics[f"vol_ratio_{interval}"] = format(vol_ratio, "f")
        metrics[f"ret_{interval}_pct"] = format(bar_return, "f")
        metrics[f"prior_runup_{interval}_pct"] = format(prior_runup, "f")
        metrics[f"recent_green_{interval}_bars"] = str(recent_green_bars)
        metrics[f"breakout_{interval}"] = str(breakout)
        metrics["stop_source"] = f"in_progress_{interval}_low"

        if atr > self.config.atr_pct_max or window_range > self.config.range_pct_max:
            reasons.append(f"{interval}_not_compressed")
        if vol_ratio < self.config.volume_multiple:
            reasons.append(f"{interval}_volume_too_low")
        if bar_return < self.config.return_pct_min:
            reasons.append(f"{interval}_push_too_small")
        if not breakout:
            reasons.append(f"{interval}_not_breakout")
        if prior_runup > self.config.prior_runup_limit_pct:
            reasons.append("already_extended")
        if bar_return > self.config.overheat_limit_pct:
            reasons.append(f"{interval}_overheated")
        if recent_green_bars > self.config.max_recent_green_bars:
            reasons.append("recent_green_stretch")

        triggered = not reasons
        return SignalDecision(
            symbol=symbol,
            triggered=triggered,
            reason="triggered" if triggered else ",".join(reasons),
            metrics=metrics,
            stop_reference_low=current_bar.low_price,
            current_price=current_bar.close_price,
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
