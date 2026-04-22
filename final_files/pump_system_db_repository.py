from __future__ import annotations

from datetime import timezone
from decimal import Decimal
from typing import Iterable

from psycopg2.extras import execute_values

import db_util
from pump_system.models import Kline


UTC = timezone.utc


class KlineRepository:
    """DB adapter that reuses db_util's pool while adding safe bulk inserts."""

    ALLOWED_TABLES = {
        "public.semi_auto_price_future_1m",
        "public.semi_auto_price_future_3m",
    }

    def __init__(self, database: str) -> None:
        self.database = database

    def healthcheck(self) -> None:
        conn = db_util.getconn(self.database)
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        finally:
            db_util.conn_pools[self.database].putconn(conn)

    def fetch_latest_timestamps(self, table_name: str) -> dict[str, object]:
        self._validate_table(table_name)
        query = f"SELECT code, MAX(da) AS da FROM {table_name} GROUP BY code"
        rows = db_util.db99fetchall_dict(self.database, query)
        return {row["code"]: row["da"] for row in rows}

    def fetch_recent_klines(self, table_name: str, symbols: list[str], limit: int, interval: str) -> list[Kline]:
        self._validate_table(table_name)
        if not symbols:
            return []

        conn = db_util.getconn(self.database)
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT code, da, op, hi, lo, cl, vol
                    FROM (
                        SELECT
                            code,
                            da,
                            op,
                            hi,
                            lo,
                            cl,
                            vol,
                            ROW_NUMBER() OVER (PARTITION BY code ORDER BY da DESC) AS rn
                        FROM {table_name}
                        WHERE code = ANY(%s)
                    ) ranked
                    WHERE rn <= %s
                    ORDER BY code, da
                    """,
                    (symbols, limit),
                )
                rows = cursor.fetchall()
        finally:
            db_util.conn_pools[self.database].putconn(conn)

        bars: list[Kline] = []
        for code, da, op, hi, lo, cl, vol in rows:
            open_time = da.replace(tzinfo=UTC)
            delta_minutes = 1 if interval == "1m" else 3
            bars.append(
                Kline(
                    symbol=code,
                    interval=interval,
                    open_time=open_time,
                    close_time=open_time,
                    open_price=Decimal(str(op)),
                    high_price=Decimal(str(hi)),
                    low_price=Decimal(str(lo)),
                    close_price=Decimal(str(cl)),
                    volume=Decimal(str(vol)),
                    closed=True,
                    event_time=None,
                )
            )
        return bars

    def bulk_insert_klines(self, table_name: str, klines: Iterable[Kline]) -> int:
        self._validate_table(table_name)
        rows = [bar.as_db_row for bar in klines]
        if not rows:
            return 0

        conn = db_util.getconn(self.database)
        try:
            with conn.cursor() as cursor:
                execute_values(
                    cursor,
                    f"""
                    INSERT INTO {table_name} (da, code, cl, hi, lo, op, vol)
                    VALUES %s
                    ON CONFLICT (code, da) DO NOTHING
                    """,
                    rows,
                )
                inserted = cursor.rowcount
            conn.commit()
            return inserted
        except Exception:
            conn.rollback()
            raise
        finally:
            db_util.conn_pools[self.database].putconn(conn)

    @classmethod
    def _validate_table(cls, table_name: str) -> None:
        if table_name not in cls.ALLOWED_TABLES:
            raise ValueError(f"Unsupported table name: {table_name}")
