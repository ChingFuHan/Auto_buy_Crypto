from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from config import Settings
from pump_system.models import Kline, SignalDecision, UTC_PLUS_8, utc_now


class SignalDecisionAuditWriter:
    """Append-only JSONL audit trail for signal decisions and order gates."""

    def __init__(self, settings: Settings, audit_dir: Path | None = None) -> None:
        self.settings = settings
        self.audit_dir = audit_dir or settings.data_dir / "audit" / "signal_decisions"

    def record_signal_decision(
        self,
        *,
        symbol: str,
        finalized_bars: list[Kline],
        current_bar: Kline | None,
        decision: SignalDecision,
    ) -> Path:
        payload = self._base_payload("SIGNAL_DECISION", symbol, current_bar)
        payload.update(
            {
                "decision": self._decision_payload(decision),
                "current_bar": self._kline_payload(current_bar),
                "finalized_window": self._finalized_window_payload(finalized_bars),
                "strategy": self._strategy_payload(),
            }
        )
        return self._append(payload, current_bar)

    def record_order_gate(
        self,
        *,
        event_type: str,
        symbol: str,
        current_bar: Kline | None,
        decision: SignalDecision | None = None,
        details: dict[str, Any] | None = None,
    ) -> Path:
        payload = self._base_payload(event_type, symbol, current_bar)
        payload.update(
            {
                "decision": self._decision_payload(decision) if decision is not None else None,
                "details": self._json_safe(details or {}),
            }
        )
        return self._append(payload, current_bar)

    def _append(self, payload: dict[str, Any], current_bar: Kline | None) -> Path:
        path = self._path_for(current_bar)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        return path

    def _path_for(self, current_bar: Kline | None) -> Path:
        stamp = current_bar.event_time or current_bar.open_time if current_bar is not None else utc_now()
        local_stamp = stamp.astimezone(UTC_PLUS_8)
        return self.audit_dir / f"signal_decisions_{self.settings.strategy_interval}_{local_stamp:%Y%m%d}.jsonl"

    def _base_payload(self, event_type: str, symbol: str, current_bar: Kline | None) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "event_type": event_type,
            "recorded_at": utc_now().isoformat(),
            "symbol": symbol,
            "strategy_interval": self.settings.strategy_interval,
            "bar_open_time": current_bar.open_time.isoformat() if current_bar is not None else None,
            "bar_event_time": current_bar.event_time.isoformat() if current_bar is not None and current_bar.event_time is not None else None,
        }

    def _strategy_payload(self) -> dict[str, Any]:
        strategy = self.settings.strategy
        return {
            "lookback": strategy.lookback,
            "breakout_lookback": strategy.breakout_lookback,
            "atr_pct_max": str(strategy.atr_pct_max),
            "range_pct_max": str(strategy.range_pct_max),
            "volume_multiple": str(strategy.volume_multiple),
            "return_pct_min": str(strategy.return_pct_min),
            "prior_runup_limit_pct": str(strategy.prior_runup_limit_pct),
            "overheat_limit_pct": str(strategy.overheat_limit_pct),
            "max_recent_green_bars": strategy.max_recent_green_bars,
        }

    def _decision_payload(self, decision: SignalDecision) -> dict[str, Any]:
        return {
            "triggered": decision.triggered,
            "reason": decision.reason,
            "metrics": self._json_safe(decision.metrics),
            "stop_reference_low": str(decision.stop_reference_low) if decision.stop_reference_low is not None else None,
            "current_price": str(decision.current_price) if decision.current_price is not None else None,
        }

    def _finalized_window_payload(self, bars: list[Kline]) -> dict[str, Any]:
        return {
            "count": len(bars),
            "first_open_time": bars[0].open_time.isoformat() if bars else None,
            "last_open_time": bars[-1].open_time.isoformat() if bars else None,
            "last_close_price": str(bars[-1].close_price) if bars else None,
            "hash": self._bars_hash(bars),
        }

    def _bars_hash(self, bars: list[Kline]) -> str:
        digest = hashlib.sha256()
        for bar in bars:
            digest.update(
                "|".join(
                    (
                        bar.symbol,
                        bar.interval,
                        bar.open_time.isoformat(),
                        str(bar.open_price),
                        str(bar.high_price),
                        str(bar.low_price),
                        str(bar.close_price),
                        str(bar.volume),
                    )
                ).encode("utf-8")
            )
            digest.update(b"\n")
        return digest.hexdigest()

    def _kline_payload(self, bar: Kline | None) -> dict[str, Any] | None:
        if bar is None:
            return None
        return {
            "symbol": bar.symbol,
            "interval": bar.interval,
            "open_time": bar.open_time.isoformat(),
            "close_time": bar.close_time.isoformat(),
            "open": str(bar.open_price),
            "high": str(bar.high_price),
            "low": str(bar.low_price),
            "close": str(bar.close_price),
            "volume": str(bar.volume),
            "closed": bar.closed,
            "event_time": bar.event_time.isoformat() if bar.event_time is not None else None,
        }

    def _json_safe(self, payload: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe[key] = value
                continue
            safe[key] = str(value)
        return safe

