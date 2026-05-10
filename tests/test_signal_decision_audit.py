import gzip
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from config import load_settings
from pump_system.audit.jsonl_parquet import maintain_jsonl_audit_dir
from pump_system.audit.signal_decision_audit import SignalDecisionAuditWriter
from pump_system.models import Kline, SignalDecision


UTC = timezone.utc


def make_bar(minute: int, closed: bool = True) -> Kline:
    open_time = datetime(2026, 5, 7, 0, 0, tzinfo=UTC) + timedelta(minutes=minute)
    return Kline(
        symbol="DOGSUSDT",
        interval="15m",
        open_time=open_time,
        close_time=open_time + timedelta(minutes=15) - timedelta(milliseconds=1),
        open_price=Decimal("0.00006000"),
        high_price=Decimal("0.00006100"),
        low_price=Decimal("0.00005900"),
        close_price=Decimal("0.00006050"),
        volume=Decimal("1000000"),
        closed=closed,
        event_time=open_time + timedelta(seconds=30),
    )


def test_signal_decision_audit_writes_jsonl_snapshot(tmp_path) -> None:
    settings = replace(load_settings(), data_dir=tmp_path)
    writer = SignalDecisionAuditWriter(settings)
    current_bar = make_bar(45, closed=False)
    finalized_bars = [make_bar(i * 15) for i in range(20)]
    decision = SignalDecision(
        symbol="DOGSUSDT",
        triggered=False,
        reason="15m_not_compressed",
        metrics={"mode": "15m_only", "ret_15m_pct": "0.010"},
        stop_reference_low=current_bar.low_price,
        current_price=current_bar.close_price,
    )

    path = writer.record_signal_decision(
        symbol="DOGSUSDT",
        finalized_bars=finalized_bars,
        current_bar=current_bar,
        decision=decision,
    )

    payload = json.loads(path.read_text(encoding="utf-8").strip())
    assert payload["event_type"] == "SIGNAL_DECISION"
    assert payload["symbol"] == "DOGSUSDT"
    assert payload["decision"]["triggered"] is False
    assert payload["decision"]["reason"] == "15m_not_compressed"
    assert payload["current_bar"]["open"] == "0.00006000"
    assert payload["finalized_window"]["count"] == 20
    assert len(payload["finalized_window"]["hash"]) == 64
    assert payload["strategy"]["return_pct_min"] == str(settings.strategy.return_pct_min)


def test_signal_audit_maintenance_archives_completed_jsonl_as_gzip(tmp_path) -> None:
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    old_jsonl = audit_dir / "signal_decisions_15m_20260508.jsonl"
    current_jsonl = audit_dir / "signal_decisions_15m_20260509.jsonl"
    old_jsonl.write_text('{"symbol":"DOGSUSDT"}\n', encoding="utf-8")
    current_jsonl.write_text('{"symbol":"HOMEUSDT"}\n', encoding="utf-8")

    result = maintain_jsonl_audit_dir(
        audit_dir=audit_dir,
        file_prefix="signal_decisions_15m",
        row_builder=lambda payload: payload,
        archive_after_days=1,
        retention_days=7,
        archive_format="gzip",
        gzip_compresslevel=1,
        now=datetime(2026, 5, 9, 8, 0, tzinfo=timezone.utc),
    )

    archive_path = audit_dir / "signal_decisions_15m_20260508.jsonl.gz"
    assert result.archived == [archive_path]
    assert not old_jsonl.exists()
    assert current_jsonl.exists()
    with gzip.open(archive_path, "rt", encoding="utf-8") as handle:
        assert handle.read() == '{"symbol":"DOGSUSDT"}\n'


def test_signal_audit_maintenance_retention_keeps_unarchived_jsonl(tmp_path) -> None:
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    unarchived_jsonl = audit_dir / "signal_decisions_15m_20260430.jsonl"
    old_archive = audit_dir / "signal_decisions_15m_20260501.jsonl.gz"
    unarchived_jsonl.write_text('{"symbol":"DOGSUSDT"}\n', encoding="utf-8")
    old_archive.write_bytes(b"compressed")

    result = maintain_jsonl_audit_dir(
        audit_dir=audit_dir,
        file_prefix="signal_decisions_15m",
        row_builder=lambda payload: payload,
        archive_after_days=30,
        retention_days=7,
        archive_format="gzip",
        gzip_compresslevel=1,
        now=datetime(2026, 5, 9, 8, 0, tzinfo=timezone.utc),
    )

    assert unarchived_jsonl.exists()
    assert not old_archive.exists()
    assert result.deleted == [old_archive]
    assert "archive is missing" in result.skipped[0]
