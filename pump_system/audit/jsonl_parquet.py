from __future__ import annotations

import gzip
import json
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from pump_system.models import UTC_PLUS_8, utc_now


JsonRowBuilder = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(slots=True)
class AuditMaintenanceResult:
    archived: list[Path] = field(default_factory=list)
    deleted: list[Path] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.archived or self.deleted)


def compact_json(payload: Any) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def maintain_jsonl_audit_dir(
    *,
    audit_dir: Path,
    file_prefix: str,
    row_builder: JsonRowBuilder,
    archive_after_days: int,
    retention_days: int,
    archive_format: str,
    gzip_compresslevel: int,
    parquet_compression: str = "snappy",
    now: datetime | None = None,
) -> AuditMaintenanceResult:
    result = AuditMaintenanceResult()
    if not audit_dir.exists():
        return result

    local_today = (now or utc_now()).astimezone(UTC_PLUS_8).date()
    archive_after_days = max(1, archive_after_days)
    archive_format = archive_format.lower()

    for path in sorted(audit_dir.glob(f"{file_prefix}_*.jsonl")):
        file_date = _file_date(path, file_prefix)
        if file_date is None:
            continue
        if (local_today - file_date).days < archive_after_days:
            continue

        archive_path = _archive_path(path, archive_format)
        if archive_path.exists():
            path.unlink()
            result.deleted.append(path)
            continue

        try:
            if archive_format == "gzip":
                _gzip_file(path, archive_path, compresslevel=gzip_compresslevel)
            elif archive_format == "parquet":
                _jsonl_to_parquet(
                    jsonl_path=path,
                    parquet_path=archive_path,
                    row_builder=row_builder,
                    compression=parquet_compression,
                )
            else:
                result.failed.append(f"{path}: unsupported archive format {archive_format}")
                continue
            path.unlink()
            result.archived.append(archive_path)
        except ModuleNotFoundError as exc:
            if exc.name == "pyarrow":
                result.skipped.append(f"{path}: pyarrow is required for parquet archival")
                break
            result.failed.append(f"{path}: {exc}")
        except Exception as exc:
            result.failed.append(f"{path}: {exc}")

    if retention_days > 0:
        for path in sorted(audit_dir.glob(f"{file_prefix}_*")):
            file_date = _file_date(path, file_prefix)
            if file_date is None:
                continue
            if (local_today - file_date).days <= retention_days:
                continue
            if path.suffix == ".jsonl" and not _has_archive(path):
                result.skipped.append(f"{path}: retention skipped because archive is missing")
                continue
            if path.suffix not in {".jsonl", ".parquet", ".gz"}:
                continue
            path.unlink()
            result.deleted.append(path)

    return result


def _gzip_file(jsonl_path: Path, gzip_path: Path, compresslevel: int) -> None:
    temp_path = gzip_path.with_name(f"{gzip_path.name}.tmp")
    try:
        with jsonl_path.open("rb") as source, temp_path.open("wb") as raw_target:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw_target,
                compresslevel=compresslevel,
                mtime=0,
            ) as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
        temp_path.replace(gzip_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _jsonl_to_parquet(
    *,
    jsonl_path: Path,
    parquet_path: Path,
    row_builder: JsonRowBuilder,
    compression: str,
) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows: list[dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid json at line {line_number}: {exc}") from exc
            rows.append(row_builder(payload))

    table = pa.Table.from_pylist(rows)
    temp_path = parquet_path.with_name(f"{parquet_path.name}.tmp")
    try:
        pq.write_table(table, temp_path, compression=compression)
    except Exception:
        if compression.lower() == "snappy":
            raise
        pq.write_table(table, temp_path, compression="snappy")
    temp_path.replace(parquet_path)


def _archive_path(jsonl_path: Path, archive_format: str) -> Path:
    if archive_format == "gzip":
        return jsonl_path.with_name(f"{jsonl_path.name}.gz")
    if archive_format == "parquet":
        return jsonl_path.with_suffix(".parquet")
    return jsonl_path.with_suffix(f".{archive_format}")


def _has_archive(jsonl_path: Path) -> bool:
    return jsonl_path.with_name(f"{jsonl_path.name}.gz").exists() or jsonl_path.with_suffix(".parquet").exists()


def _file_date(path: Path, file_prefix: str) -> date | None:
    name = path.name
    prefix = f"{file_prefix}_"
    if not name.startswith(prefix):
        return None
    token = name[len(prefix) : len(prefix) + 8]
    if len(token) != 8 or not token.isdigit():
        return None
    try:
        return datetime.strptime(token, "%Y%m%d").date()
    except ValueError:
        return None
