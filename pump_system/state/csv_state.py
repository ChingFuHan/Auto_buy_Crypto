from __future__ import annotations

import asyncio
import csv
import os
import tempfile
from pathlib import Path


class AtomicCsvState:
    """Atomic CSV store for small runtime state tables."""

    def __init__(self, path: Path, fieldnames: list[str]) -> None:
        self.path = path
        self.fieldnames = fieldnames
        self._lock = asyncio.Lock()

    async def load_rows(self) -> list[dict[str, str]]:
        async with self._lock:
            return self._read_rows()

    async def replace_rows(self, rows: list[dict[str, str]]) -> None:
        async with self._lock:
            self._write_rows(rows)

    async def upsert_row(self, key_field: str, row: dict[str, str]) -> None:
        async with self._lock:
            rows = self._read_rows()
            replaced = False
            for index, current in enumerate(rows):
                if current.get(key_field) == row.get(key_field):
                    rows[index] = row
                    replaced = True
                    break
            if not replaced:
                rows.append(row)
            self._write_rows(rows)

    def _read_rows(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []
        with self.path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return [dict(row) for row in reader]

    def _write_rows(self, rows: list[dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix=self.path.stem, suffix=".tmp", dir=self.path.parent)
        os.close(fd)
        try:
            with open(temp_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=self.fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
            os.replace(temp_path, self.path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
