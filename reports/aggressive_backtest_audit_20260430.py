"""Aggressive Breakout 可審核回測 audit script (task_temp_v4.md).

Subcommands:
  inventory   Phase 1: DB 盤點 (schema raw dump, row counts, min/max, per-symbol stats, gaps)
  dryrun      Phase 2: dry-run estimate (no DB writes; check Binance availability lazily)
  backfill    Phase 2: append-only backfill via existing pump_system pipeline
  audit       Phase 3-6: run full backtest (Layer 1 / 1.5 / 2 + sanity + buckets)
  audit-live-safe
              Phase 3-6: low-memory batched audit for running alongside live bot

Reproducibility:
  - read-only DB unless `backfill` invoked
  - all params via CLI flags / module constants
  - intermediate results pickled under reports/cache_<YYYYMMDD>/
"""

from __future__ import annotations
import argparse
import gc
import json
import os
import pickle
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REPORT_DATE = "20260430"
REPORT_DIR = ROOT / "reports"
CACHE_DIR = REPORT_DIR / f"cache_{REPORT_DATE}"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# SignalEngine 等價常數 (Phase 3)
LOOKBACK = 20
BREAKOUT_LOOKBACK = 12
PRIOR_RUNUP_LOOKBACK = 5

UNI_RET_MIN = 0.017
UNI_VOL_RATIO_MIN = 2.0
UNI_PRIOR_RUNUP_MAX = 0.040
UNI_RECENT_GREEN_MAX = 3
UNI_ATR_MAX = 0.015

OVERHEAT_LIMIT_PCT = 0.060
RANGE_LIMIT_PCT = 0.035

COST_TOTAL_PCT = 0.006
HORIZONS = [4, 16, 96]

# Sanity tolerance
SANITY_RET_TOL = 0.0005   # 0.05 percentage point
SANITY_RANGE_TOL = 0.0005
SANITY_VOL_RATIO_REL_TOL = 0.01

# Dry-run hard caps (Phase 2)
DRY_API_CALL_CAP = 50_000
DRY_NEW_ROWS_CAP = 2_000_000
DRY_WALLCLOCK_HOURS_CAP = 2
DRY_TABLE_GROWTH_FRAC_CAP = 0.50

DB_NAME = "daily"
TABLES = {
    "15m": "public.semi_auto_price_future_15m",
    "3m": "public.semi_auto_price_future_3m",
    "1m": "public.semi_auto_price_future_1m",
}


def _now_utc():
    return datetime.now(timezone.utc)


def _conn():
    import db_util
    return db_util.getconn(DB_NAME)


def _query_all(sql: str, args=None):
    import db_util
    conn = db_util.getconn(DB_NAME)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall() if cur.description else []
        return cols, rows
    finally:
        import db_util as _du
        _du.conn_pools[DB_NAME].putconn(conn)


# ---------- Phase 1 ----------

def cmd_inventory(args):
    """Phase 1 — DB 盤點"""
    out: Dict[str, dict] = {}
    print(f"=== Phase 1 inventory @ {_now_utc().isoformat()} ===")
    for label, table in TABLES.items():
        info: dict = {"table": table}
        # schema raw dump (information_schema)
        cols_q = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position;
        """
        c, rows = _query_all(cols_q, (table.split(".")[-1],))
        info["columns_raw"] = [dict(zip(c, r)) for r in rows]

        # primary key + unique constraints
        pk_q = """
            SELECT con.conname, con.contype,
                   pg_get_constraintdef(con.oid) AS def
            FROM pg_constraint con
            JOIN pg_class cls ON cls.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = cls.relnamespace
            WHERE nsp.nspname='public' AND cls.relname=%s
              AND con.contype IN ('p','u');
        """
        c, rows = _query_all(pk_q, (table.split(".")[-1],))
        info["constraints"] = [dict(zip(c, r)) for r in rows]

        # indexes
        idx_q = """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname='public' AND tablename=%s;
        """
        c, rows = _query_all(idx_q, (table.split(".")[-1],))
        info["indexes"] = [dict(zip(c, r)) for r in rows]

        # row count, min/max da, distinct code
        c, rows = _query_all(
            f"SELECT COUNT(*), MIN(da), MAX(da), COUNT(DISTINCT code) FROM {table};"
        )
        rc, mn, mx, dc = rows[0]
        info["row_count"] = rc
        info["min_da"] = str(mn) if mn else None
        info["max_da"] = str(mx) if mx else None
        info["distinct_code_count"] = dc

        # per-symbol stats (top/bottom by count, recent gaps)
        c, rows = _query_all(
            f"""SELECT code, COUNT(*) AS cnt, MIN(da) AS mn, MAX(da) AS mx
                 FROM {table} GROUP BY code;"""
        )
        per_sym = [(code, cnt, mn, mx) for code, cnt, mn, mx in rows]
        info["per_symbol_count"] = len(per_sym)
        if per_sym:
            counts = sorted(c2 for _, c2, _, _ in per_sym)
            info["per_symbol_count_min"] = counts[0]
            info["per_symbol_count_p50"] = counts[len(counts) // 2]
            info["per_symbol_count_max"] = counts[-1]
            info["per_symbol_count_p10"] = counts[max(0, len(counts) // 10 - 1)]
            # most recent symbol max(da)
            latest = max(mx for _, _, _, mx in per_sym)
            info["latest_symbol_max_da"] = str(latest)
            stale_cutoff = latest - timedelta(days=2)
            info["stale_symbols_count"] = sum(1 for _, _, _, mx in per_sym if mx < stale_cutoff)
            # earliest symbol min(da)
            earliest = min(mn for _, _, mn, _ in per_sym if mn is not None)
            info["earliest_symbol_min_da"] = str(earliest)

        # SOLVUSDT specific (sanity)
        c, rows = _query_all(
            f"SELECT MIN(da), MAX(da), COUNT(*) FROM {table} WHERE code='SOLVUSDT';"
        )
        if rows:
            info["SOLVUSDT_min"] = str(rows[0][0]) if rows[0][0] else None
            info["SOLVUSDT_max"] = str(rows[0][1]) if rows[0][1] else None
            info["SOLVUSDT_count"] = rows[0][2]

        out[label] = info
        print(f"  {label} {table}: rows={rc:,} symbols={dc} min={info['min_da']} max={info['max_da']}")

    cache_path = CACHE_DIR / "phase1_inventory.pkl"
    with open(cache_path, "wb") as f:
        pickle.dump(out, f)
    json_path = CACHE_DIR / "phase1_inventory.json"
    json_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"=> {cache_path}")
    print(f"=> {json_path}")
    return out


# ---------- Phase 2 ----------

def cmd_dryrun(args):
    """Phase 2 — dry-run estimate"""
    print(f"=== Phase 2 dry-run @ {_now_utc().isoformat()} ===")
    inv_path = CACHE_DIR / "phase1_inventory.pkl"
    if not inv_path.exists():
        print("[ERR] run inventory first")
        sys.exit(2)
    with open(inv_path, "rb") as f:
        inv = pickle.load(f)

    # Targets:
    #   15m: 補到 max possible (Binance 通常每 symbol 過去 ~4 年；保守只補到當前已存資料的「最早 - 30 天」回推 N 天)
    #   3m:  覆蓋 15m 回測期間
    # Strategy: 對每個 already-tracked symbol，計算「現有 min_da -> 我們希望的 target_min_da」缺多少 bars。
    # Target span:
    #   15m → 從 latest_symbol_max_da 往回 365 天 (一年)
    #   3m  → 同 15m 期間 (但 3m 資料量大, 要嚴格估算)

    horizon_days_15m = args.days_15m
    horizon_days_3m = args.days_3m
    forward_only = args.forward_only

    estimates = {}
    for label, target_days in [("15m", horizon_days_15m), ("3m", horizon_days_3m)]:
        info = inv[label]
        latest_overall = datetime.fromisoformat(info["latest_symbol_max_da"].replace(" ", "T"))
        # "now" 估計：用 utc now，避免 latest 本身就是 stale
        now_utc = _now_utc().replace(tzinfo=None)
        target_min = (latest_overall - timedelta(days=target_days)) if not forward_only else now_utc + timedelta(days=999)  # forward only: skip backward
        target_max = now_utc  # 補到當下
        c, rows = _query_all(
            f"""SELECT code, MIN(da), MAX(da) FROM {TABLES[label]} GROUP BY code;"""
        )
        bar_seconds = 15 * 60 if label == "15m" else (3 * 60 if label == "3m" else 60)
        bar_per_call = 1500
        total_new_rows = 0
        symbol_calls = 0
        symbol_with_back_gap = 0
        symbol_with_fwd_gap = 0
        for code, cur_min, cur_max in rows:
            if cur_min is None:
                continue
            cur_min_dt = cur_min if isinstance(cur_min, datetime) else datetime.fromisoformat(str(cur_min))
            cur_max_dt = cur_max if isinstance(cur_max, datetime) else datetime.fromisoformat(str(cur_max))
            # backward fill
            if not forward_only and cur_min_dt > target_min:
                back_secs = (cur_min_dt - target_min).total_seconds()
                back_bars = int(back_secs // bar_seconds)
                total_new_rows += back_bars
                symbol_calls += (back_bars + bar_per_call - 1) // bar_per_call
                symbol_with_back_gap += 1
            # forward fill
            if cur_max_dt < target_max:
                fwd_secs = (target_max - cur_max_dt).total_seconds()
                fwd_bars = int(fwd_secs // bar_seconds)
                total_new_rows += fwd_bars
                symbol_calls += (fwd_bars + bar_per_call - 1) // bar_per_call
                symbol_with_fwd_gap += 1

        est_secs = symbol_calls * 0.4
        estimates[label] = {
            "target_days": target_days,
            "forward_only": forward_only,
            "target_min_da": str(target_min) if not forward_only else None,
            "target_max_da": str(target_max),
            "symbols_with_backward_gap": symbol_with_back_gap,
            "symbols_with_forward_gap": symbol_with_fwd_gap,
            "symbols_total": len(rows),
            "est_api_calls": symbol_calls,
            "est_new_rows": total_new_rows,
            "est_wallclock_secs": est_secs,
            "est_wallclock_hr": round(est_secs / 3600, 2),
            "current_rows": info["row_count"],
            "growth_frac": (total_new_rows / info["row_count"]) if info["row_count"] else 0.0,
        }
        print(f"  {label}: back_gap={symbol_with_back_gap} fwd_gap={symbol_with_fwd_gap}/{len(rows)} api_calls~{symbol_calls:,} new_rows~{total_new_rows:,} wallclock~{est_secs/60:.1f}min growth={estimates[label]['growth_frac']*100:.1f}%")

    # cap check
    breaches = []
    total_calls = sum(e["est_api_calls"] for e in estimates.values())
    total_rows = sum(e["est_new_rows"] for e in estimates.values())
    total_secs = sum(e["est_wallclock_secs"] for e in estimates.values())
    if total_calls > DRY_API_CALL_CAP:
        breaches.append(f"API calls {total_calls:,} > cap {DRY_API_CALL_CAP:,}")
    if total_rows > DRY_NEW_ROWS_CAP:
        breaches.append(f"new rows {total_rows:,} > cap {DRY_NEW_ROWS_CAP:,}")
    if total_secs > DRY_WALLCLOCK_HOURS_CAP * 3600:
        breaches.append(f"wallclock {total_secs/3600:.2f}h > cap {DRY_WALLCLOCK_HOURS_CAP}h")
    for label, e in estimates.items():
        if e["growth_frac"] > DRY_TABLE_GROWTH_FRAC_CAP:
            breaches.append(f"{label} table growth {e['growth_frac']*100:.1f}% > cap {DRY_TABLE_GROWTH_FRAC_CAP*100:.0f}%")

    out = {
        "estimates": estimates,
        "totals": {
            "api_calls": total_calls,
            "new_rows": total_rows,
            "wallclock_secs": total_secs,
            "wallclock_hr": round(total_secs / 3600, 2),
        },
        "caps": {
            "api_calls": DRY_API_CALL_CAP,
            "new_rows": DRY_NEW_ROWS_CAP,
            "wallclock_hr": DRY_WALLCLOCK_HOURS_CAP,
            "table_growth_frac": DRY_TABLE_GROWTH_FRAC_CAP,
        },
        "breaches": breaches,
        "approved_to_backfill": len(breaches) == 0,
    }
    cache_path = CACHE_DIR / "phase2_dryrun.pkl"
    with open(cache_path, "wb") as f:
        pickle.dump(out, f)
    json_path = CACHE_DIR / "phase2_dryrun.json"
    json_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"=> {cache_path}")
    print(f"=> {json_path}")
    if breaches:
        print(f"[BLOCKED] dry-run breaches: {breaches}")
    else:
        print("[OK] dry-run within caps; backfill may proceed")
    return out


# ---------- Phase 2: backfill (forward-only, append-only) ----------

def cmd_backfill(args):
    """Phase 2 backfill — forward-only fill of 15m + 3m gaps via Binance public klines."""
    import httpx
    from decimal import Decimal
    from pump_system.db.repository import KlineRepository
    from pump_system.models import Kline, UTC_PLUS_8

    print(f"=== Phase 2 backfill (forward-only) @ {_now_utc().isoformat()} ===")

    # Pre-snapshot
    pre = {}
    for label, table in [("15m", TABLES["15m"]), ("3m", TABLES["3m"])]:
        c, rows = _query_all(f"SELECT COUNT(*), MIN(da), MAX(da), COUNT(DISTINCT code) FROM {table};")
        pre[label] = {"row_count": rows[0][0], "min_da": str(rows[0][1]), "max_da": str(rows[0][2]), "distinct": rows[0][3]}
        print(f"  PRE  {label}: rows={pre[label]['row_count']:,} min={pre[label]['min_da']} max={pre[label]['max_da']} dc={pre[label]['distinct']}")

    repo = KlineRepository(database=DB_NAME)
    base = "https://fapi.binance.com"
    client = httpx.Client(base_url=base, timeout=httpx.Timeout(20.0, connect=10.0))

    interval_ms_map = {"15m": 15 * 60_000, "3m": 3 * 60_000}
    now_ms = int(time.time() * 1000)

    inserted_summary = {"15m": 0, "3m": 0}
    api_calls = {"15m": 0, "3m": 0}

    for label, target_table in [("15m", TABLES["15m"]), ("3m", TABLES["3m"])]:
        interval_ms = interval_ms_map[label]
        # current per-symbol max
        c, rows = _query_all(f"SELECT code, MAX(da) FROM {target_table} GROUP BY code;")
        # filter symbols with forward gap
        gap_syms = []
        for code, cur_max in rows:
            if cur_max is None:
                continue
            cur_max_dt = cur_max if isinstance(cur_max, datetime) else datetime.fromisoformat(str(cur_max))
            # cur_max is naive UTC+8 wall-clock per repository convention
            cur_max_aware = cur_max_dt.replace(tzinfo=UTC_PLUS_8)
            cur_max_utc_ms = int(cur_max_aware.timestamp() * 1000)
            if cur_max_utc_ms + interval_ms < now_ms - interval_ms:
                gap_syms.append((code, cur_max_utc_ms))
        print(f"  {label}: {len(gap_syms)} symbols need forward fill")
        if not gap_syms:
            continue

        for idx, (code, cur_max_utc_ms) in enumerate(gap_syms, 1):
            start_ms = cur_max_utc_ms + interval_ms
            current_open_ms = (now_ms // interval_ms) * interval_ms
            if start_ms >= current_open_ms:
                continue
            sym_inserted = 0
            sym_calls = 0
            cursor_ms = start_ms
            retries = 0
            while cursor_ms < current_open_ms:
                try:
                    r = client.get("/fapi/v1/klines", params={
                        "symbol": code,
                        "interval": label,
                        "startTime": cursor_ms,
                        "endTime": current_open_ms - 1,
                        "limit": 1500,
                    })
                except Exception as e:
                    retries += 1
                    if retries > 3:
                        print(f"    [BLOCKED] {code}: net error retry>3: {e}")
                        break
                    time.sleep(1.0 * retries)
                    continue
                sym_calls += 1
                api_calls[label] += 1
                if r.status_code == 429 or r.status_code == 418:
                    retries += 1
                    if retries > 3:
                        print(f"    [BLOCKED] {code}: rate-limit retry>3 status={r.status_code}")
                        break
                    sleep_s = 2 ** retries
                    print(f"    rate-limit {r.status_code} on {code}, sleep {sleep_s}s")
                    time.sleep(sleep_s)
                    continue
                if r.status_code != 200:
                    retries += 1
                    if retries > 3:
                        print(f"    [BLOCKED] {code}: http {r.status_code} retry>3: {r.text[:120]}")
                        break
                    time.sleep(1.0 * retries)
                    continue
                retries = 0
                rows_data = r.json()
                if not rows_data:
                    break
                bars = []
                for row in rows_data:
                    close_time_ms = int(row[6])
                    if close_time_ms >= current_open_ms:
                        continue  # skip in-progress bar
                    open_time_ms = int(row[0])
                    bars.append(Kline(
                        symbol=code,
                        interval=label,
                        open_time=datetime.fromtimestamp(open_time_ms / 1000, tz=timezone.utc),
                        close_time=datetime.fromtimestamp(close_time_ms / 1000, tz=timezone.utc),
                        open_price=Decimal(str(row[1])),
                        high_price=Decimal(str(row[2])),
                        low_price=Decimal(str(row[3])),
                        close_price=Decimal(str(row[4])),
                        volume=Decimal(str(row[5])),
                        closed=True,
                        event_time=None,
                    ))
                if bars:
                    inserted = repo.bulk_insert_klines(target_table, bars)
                    sym_inserted += inserted
                cursor_ms = int(rows_data[-1][0]) + interval_ms
                if len(rows_data) < 1500:
                    break
                # gentle pacing
                time.sleep(0.05)

            inserted_summary[label] += sym_inserted
            if idx % 50 == 0 or idx == len(gap_syms):
                print(f"    progress {label} {idx}/{len(gap_syms)} cumul_inserted={inserted_summary[label]:,} calls={api_calls[label]}")

    client.close()

    # Post-snapshot
    post = {}
    for label, table in [("15m", TABLES["15m"]), ("3m", TABLES["3m"])]:
        c, rows = _query_all(f"SELECT COUNT(*), MIN(da), MAX(da), COUNT(DISTINCT code) FROM {table};")
        post[label] = {
            "row_count": rows[0][0], "min_da": str(rows[0][1]), "max_da": str(rows[0][2]), "distinct": rows[0][3],
            "inserted": inserted_summary[label], "api_calls": api_calls[label],
        }
        print(f"  POST {label}: rows={post[label]['row_count']:,} min={post[label]['min_da']} max={post[label]['max_da']} dc={post[label]['distinct']} inserted={inserted_summary[label]:,}")

    out = {"pre": pre, "post": post, "inserted": inserted_summary, "api_calls": api_calls}
    cache_path = CACHE_DIR / "phase2_backfill_result.json"
    cache_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"=> {cache_path}")
    return out


# ---------- Phase 3-6: audit (Layer 1 / 1.5 / 2, sanity, buckets) ----------

def _streak(green_arr):
    """Consecutive True streak ending at each position."""
    n = len(green_arr)
    out = [0] * n
    cur = 0
    for i in range(n):
        cur = (cur + 1) if green_arr[i] else 0
        out[i] = cur
    return out


def _bucket(range_pct, ret):
    if range_pct <= RANGE_LIMIT_PCT and ret <= OVERHEAT_LIMIT_PCT:
        return 'Baseline'
    if range_pct > RANGE_LIMIT_PCT and ret <= OVERHEAT_LIMIT_PCT:
        return 'A'
    if range_pct <= RANGE_LIMIT_PCT and ret > OVERHEAT_LIMIT_PCT:
        return 'B'
    return 'C'


def _bucket_stats(sub, entry_col, horizon):
    """Compute per-bucket stats for one layer/horizon slice."""
    import numpy as np
    results = {}
    for bkt in ['Baseline', 'A', 'B', 'C']:
        s = sub[sub['bucket'] == bkt].copy()
        exit_col = f'exit_cl_{horizon}'
        mfe_col = f'mfe_hi_{horizon}'
        mae_col = f'mae_lo_{horizon}'
        s = s[s[exit_col].notna()]
        if len(s) == 0:
            results[bkt] = {'N': 0}
            continue
        entry = s[entry_col]
        exit_cl = s[exit_col]
        mfe = s[mfe_col]
        mae = s[mae_col]
        bar_low = s['bar_low']
        stop_reference = s['stop_reference'] if 'stop_reference' in s.columns else bar_low
        ret_raw = (exit_cl - entry) / entry
        ret_net = ret_raw - COST_TOTAL_PCT
        mfe_pct = (mfe - entry) / entry
        mae_pct = (mae - entry) / entry
        hit3 = mae <= entry * 0.97
        hit5 = mae <= entry * 0.95
        hit_bl = mae <= bar_low
        hit_stop_ref = mae <= stop_reference
        false3 = hit3 & (exit_cl > entry * 0.97)
        false_stop_ref = hit_stop_ref & (exit_cl > stop_reference)
        std = ret_net.std()
        results[bkt] = {
            'N': int(len(s)),
            'win_rate': float((ret_net > 0).mean()),
            'mean_ret': float(ret_net.mean()),
            'median_ret': float(ret_net.median()),
            'std': float(std),
            'expectancy': float(ret_net.mean()),
            'mfe_median': float(mfe_pct.median()),
            'mfe_p90': float(mfe_pct.quantile(0.9)),
            'mae_median': float(mae_pct.median()),
            'mae_p10': float(mae_pct.quantile(0.1)),
            'stop_3pct_rate': float(hit3.mean()),
            'stop_5pct_rate': float(hit5.mean()),
            'bar_low_stop_rate': float(hit_bl.mean()),
            'stop_reference_rate': float(hit_stop_ref.mean()),
            'false_stop_3pct_rate': float(false3.mean()),
            'false_stop_reference_rate': float(false_stop_ref.mean()),
            'sharpe': float(ret_net.mean() / std) if std > 0 else 0.0,
        }
    return results


def _build_candidates_from_15m(df_all):
    """Build 15m candidate rows from a symbol-batched 15m dataframe."""
    import numpy as np
    import pandas as pd

    all_cands = []
    selected_cols = [
        'symbol', 'da', 'bar_idx', 'bucket',
        'atr_pct', 'range_pct', 'ret', 'vol_ratio',
        'vol', 'avg_vol20', 'breakout', 'breakout_threshold',
        'prior_runup', 'recent_green',
        'op', 'hi', 'lo', 'cl', 'prev_close', 'bar_low',
    ] + [f'exit_cl_{h}' for h in HORIZONS] \
      + [f'mfe_hi_{h}' for h in HORIZONS] \
      + [f'mae_lo_{h}' for h in HORIZONS]

    for symbol, grp in df_all.groupby('code', sort=False):
        df = grp.sort_values('da').reset_index(drop=True)
        if len(df) < LOOKBACK + 1:
            continue
        bar_atr = (df['hi'] - df['lo']) / df['cl'].replace(0, np.nan)
        df['atr_pct'] = bar_atr.rolling(LOOKBACK).mean().shift(1)
        hi_r = df['hi'].rolling(LOOKBACK)
        lo_r = df['lo'].rolling(LOOKBACK)
        df['range_pct'] = (hi_r.max().shift(1) - lo_r.min().shift(1)) / lo_r.min().shift(1).replace(0, np.nan)
        df['avg_vol20'] = df['vol'].rolling(LOOKBACK).mean().shift(1)
        df['vol_ratio'] = df['vol'] / df['avg_vol20'].replace(0, np.nan)
        df['ret'] = df['cl'].pct_change()
        hi_bl = df['hi'].rolling(BREAKOUT_LOOKBACK).max().shift(1)
        df['breakout_threshold'] = hi_bl
        df['breakout'] = df['hi'] > hi_bl
        hi5 = df['hi'].rolling(PRIOR_RUNUP_LOOKBACK).max().shift(1)
        lo5 = df['lo'].rolling(PRIOR_RUNUP_LOOKBACK).min().shift(1)
        df['prior_runup'] = (hi5 - lo5) / lo5.replace(0, np.nan)
        green = (df['cl'].values > df['op'].values)
        streak = _streak(green)
        df['recent_green'] = [0] + streak[:-1]
        for h in HORIZONS:
            df[f'exit_cl_{h}'] = df['cl'].shift(-h)
            df[f'mfe_hi_{h}'] = df['hi'].rolling(h).max().shift(-h)
            df[f'mae_lo_{h}'] = df['lo'].rolling(h).min().shift(-h)
        df['prev_close'] = df['cl'].shift(1)
        df['bar_low'] = df['lo']
        df['symbol'] = symbol
        df['bar_idx'] = df.index

        mask = (
            df['atr_pct'].notna() & df['range_pct'].notna() &
            df['vol_ratio'].notna() & df['ret'].notna() &
            df['avg_vol20'].notna() & df['breakout_threshold'].notna() &
            (df['ret'] >= UNI_RET_MIN) &
            (df['vol_ratio'] >= UNI_VOL_RATIO_MIN) &
            df['breakout'] &
            (df['prior_runup'] <= UNI_PRIOR_RUNUP_MAX) &
            (df['recent_green'] <= UNI_RECENT_GREEN_MAX) &
            (df['atr_pct'] <= UNI_ATR_MAX)
        )
        sub = df[mask].copy()
        if len(sub):
            sub['bucket'] = sub.apply(lambda r: _bucket(r['range_pct'], r['ret']), axis=1)
            all_cands.append(sub[selected_cols])

    if not all_cands:
        return pd.DataFrame(columns=[c if c != 'cl' else 'entry_l1' for c in selected_cols] + ['entry_l15'])

    df_c = pd.concat(all_cands, ignore_index=True)
    df_c.rename(columns={'cl': 'entry_l1'}, inplace=True)
    df_c['entry_l15'] = df_c['prev_close'] * (1 + UNI_RET_MIN)
    return df_c


def _build_layer2_from_candidates(df_c, df3):
    """Build Layer 2 trigger rows using batched 3m data."""
    import numpy as np
    import pandas as pd

    if len(df_c) == 0 or len(df3) == 0:
        return pd.DataFrame()

    df3_by_sym = {
        sym: grp.sort_values('da').reset_index(drop=True)
        for sym, grp in df3.groupby('code')
    }
    layer2_rows = []
    interval_3m_delta = timedelta(minutes=3)
    interval_15m_delta = timedelta(minutes=15)

    for _, cand in df_c.iterrows():
        sym = cand['symbol']
        if sym not in df3_by_sym:
            continue

        bar_da = cand['da']
        prev_cl = float(cand['prev_close'])
        avg_vol20 = float(cand['avg_vol20'])
        breakout_threshold = float(cand['breakout_threshold'])
        ret_trigger_price = prev_cl * (1 + UNI_RET_MIN)

        trigger_found_opt = False
        trigger_found_con = False
        opt_row = None
        con_row = None
        cum_vol = 0.0
        cum_hi = -np.inf
        cum_lo = np.inf

        bar_end = bar_da + interval_15m_delta - interval_3m_delta
        df3s = df3_by_sym[sym]
        sub3 = df3s[(df3s['da'] >= bar_da) & (df3s['da'] <= bar_end)]

        for _, r3 in sub3.iterrows():
            cum_vol += float(r3['vol'])
            cum_hi = max(cum_hi, float(r3['hi']))
            cum_lo = min(cum_lo, float(r3['lo']))

            ret_close = (float(r3['cl']) - prev_cl) / prev_cl if prev_cl > 0 else 0.0
            ret_high = (cum_hi - prev_cl) / prev_cl if prev_cl > 0 else 0.0
            volume_ratio_at_trigger = cum_vol / avg_vol20 if avg_vol20 > 0 else 0.0
            volume_ok = volume_ratio_at_trigger >= UNI_VOL_RATIO_MIN
            breakout_ok = cum_hi > breakout_threshold

            if (
                not trigger_found_con
                and volume_ok
                and breakout_ok
                and ret_close >= UNI_RET_MIN
            ):
                trigger_found_con = True
                con_row = {
                    'trigger_da': r3['da'],
                    'trigger_offset_min': int((r3['da'] - bar_da).total_seconds() // 60),
                    'entry_price': float(r3['cl']),
                    'stop_reference': float(cum_lo),
                    'entry_mode': 'conservative',
                    'ret_at_trigger': float(ret_close),
                    'volume_ratio_at_trigger': float(volume_ratio_at_trigger),
                    'cum_volume_at_trigger': float(cum_vol),
                    'cum_high_at_trigger': float(cum_hi),
                    'breakout_threshold': float(breakout_threshold),
                    'breakout_at_trigger': bool(breakout_ok),
                }

            if (
                not trigger_found_opt
                and volume_ok
                and breakout_ok
                and ret_high >= UNI_RET_MIN
            ):
                trigger_found_opt = True
                threshold_price = max(ret_trigger_price, breakout_threshold)
                opt_row = {
                    'trigger_da': r3['da'],
                    'trigger_offset_min': int((r3['da'] - bar_da).total_seconds() // 60),
                    'entry_price': float(threshold_price),
                    'stop_reference': float(cum_lo),
                    'entry_mode': 'optimistic',
                    'ret_at_trigger': float(ret_high),
                    'volume_ratio_at_trigger': float(volume_ratio_at_trigger),
                    'cum_volume_at_trigger': float(cum_vol),
                    'cum_high_at_trigger': float(cum_hi),
                    'breakout_threshold': float(breakout_threshold),
                    'breakout_at_trigger': bool(breakout_ok),
                }

        base_row = {
            'symbol': sym,
            'bar_da': bar_da,
            'bucket': cand['bucket'],
            'atr_pct': cand['atr_pct'],
            'range_pct': cand['range_pct'],
            'ret': cand['ret'],
            'vol_ratio': cand['vol_ratio'],
            'vol': cand['vol'],
            'avg_vol20': cand['avg_vol20'],
            'breakout': cand['breakout'],
            'breakout_threshold': cand['breakout_threshold'],
            'prior_runup': cand['prior_runup'],
            'recent_green': cand['recent_green'],
            'layer': 'L2',
        }
        base_row.update({f'exit_cl_{h}': cand[f'exit_cl_{h}'] for h in HORIZONS})
        base_row.update({f'mfe_hi_{h}': cand[f'mfe_hi_{h}'] for h in HORIZONS})
        base_row.update({f'mae_lo_{h}': cand[f'mae_lo_{h}'] for h in HORIZONS})
        base_row['bar_low'] = cand['bar_low']

        for trow in [opt_row, con_row]:
            if trow is not None:
                layer2_rows.append({**base_row, **trow, 'entry_l2': trow['entry_price']})

    return pd.DataFrame(layer2_rows)


def _compute_audit_stats(df_c, df_l2):
    stats_l1 = {h: _bucket_stats(df_c, 'entry_l1', h) for h in HORIZONS}
    stats_l15 = {h: _bucket_stats(df_c, 'entry_l15', h) for h in HORIZONS}
    stats_l2_opt = {}
    stats_l2_con = {}
    if len(df_l2) > 0:
        df_l2_opt = df_l2[df_l2['entry_mode'] == 'optimistic'].copy()
        df_l2_con = df_l2[df_l2['entry_mode'] == 'conservative'].copy()
        stats_l2_opt = {h: _bucket_stats(df_l2_opt, 'entry_l2', h) for h in HORIZONS}
        stats_l2_con = {h: _bucket_stats(df_l2_con, 'entry_l2', h) for h in HORIZONS}
    return stats_l1, stats_l15, stats_l2_opt, stats_l2_con


def _print_layer_summary(label, stats):
    print(f"  {label}:")
    for h in HORIZONS:
        for bkt in ['Baseline', 'A', 'B', 'C']:
            s = stats.get(h, {}).get(bkt, {})
            if s.get('N', 0) > 0:
                fsr = s.get('false_stop_reference_rate')
                suffix = f" false_stop_ref={fsr*100:.1f}%" if fsr is not None else ""
                print(f"    {bkt} {h}bar: N={s['N']} exp={s['expectancy']*100:.2f}% median={s['median_ret']*100:.2f}%{suffix}")


def _batched(seq, size):
    for i in range(0, len(seq), size):
        yield i, seq[i:i + size]


def cmd_audit(args):
    """Phase 3-6: full backtest + sanity + Layer 1/1.5/2 + report."""
    import numpy as np
    import pandas as pd

    print(f"=== Phase 3-6 audit @ {_now_utc().isoformat()} ===")
    t0 = time.time()

    # ---- Load 15m ----
    print("Loading 15m data...")
    _, rows = _query_all(
        f"SELECT code, da, op, hi, lo, cl, vol FROM {TABLES['15m']} ORDER BY code, da"
    )
    df_all = pd.DataFrame(rows, columns=['code', 'da', 'op', 'hi', 'lo', 'cl', 'vol'])
    df_all[['op', 'hi', 'lo', 'cl', 'vol']] = df_all[['op', 'hi', 'lo', 'cl', 'vol']].astype(float)
    print(f"  {len(df_all):,} rows, {df_all['code'].nunique()} symbols  {time.time()-t0:.1f}s")

    # ---- Per-symbol rolling metrics → candidates ----
    all_cands = []
    for symbol, grp in df_all.groupby('code', sort=False):
        df = grp.sort_values('da').reset_index(drop=True)
        n = len(df)
        if n < LOOKBACK + 1:
            continue
        bar_atr = (df['hi'] - df['lo']) / df['cl'].replace(0, np.nan)
        df['atr_pct'] = bar_atr.rolling(LOOKBACK).mean().shift(1)
        hi_r = df['hi'].rolling(LOOKBACK)
        lo_r = df['lo'].rolling(LOOKBACK)
        df['range_pct'] = (hi_r.max().shift(1) - lo_r.min().shift(1)) / lo_r.min().shift(1).replace(0, np.nan)
        df['avg_vol20'] = df['vol'].rolling(LOOKBACK).mean().shift(1)
        df['vol_ratio'] = df['vol'] / df['avg_vol20'].replace(0, np.nan)
        df['ret'] = df['cl'].pct_change()
        hi_bl = df['hi'].rolling(BREAKOUT_LOOKBACK).max().shift(1)
        df['breakout_threshold'] = hi_bl
        df['breakout'] = df['hi'] > hi_bl
        hi5 = df['hi'].rolling(PRIOR_RUNUP_LOOKBACK).max().shift(1)
        lo5 = df['lo'].rolling(PRIOR_RUNUP_LOOKBACK).min().shift(1)
        df['prior_runup'] = (hi5 - lo5) / lo5.replace(0, np.nan)
        green = (df['cl'].values > df['op'].values)
        streak = _streak(green)
        df['recent_green'] = [0] + streak[:-1]
        for h in HORIZONS:
            df[f'exit_cl_{h}'] = df['cl'].shift(-h)
            df[f'mfe_hi_{h}'] = df['hi'].rolling(h).max().shift(-h)
            df[f'mae_lo_{h}'] = df['lo'].rolling(h).min().shift(-h)
        df['prev_close'] = df['cl'].shift(1)
        df['bar_low'] = df['lo']
        df['symbol'] = symbol
        df['bar_idx'] = df.index

        mask = (
            df['atr_pct'].notna() & df['range_pct'].notna() &
            df['vol_ratio'].notna() & df['ret'].notna() &
            df['avg_vol20'].notna() & df['breakout_threshold'].notna() &
            (df['ret'] >= UNI_RET_MIN) &
            (df['vol_ratio'] >= UNI_VOL_RATIO_MIN) &
            df['breakout'] &
            (df['prior_runup'] <= UNI_PRIOR_RUNUP_MAX) &
            (df['recent_green'] <= UNI_RECENT_GREEN_MAX) &
            (df['atr_pct'] <= UNI_ATR_MAX)
        )
        sub = df[mask].copy()
        if len(sub):
            sub['bucket'] = sub.apply(lambda r: _bucket(r['range_pct'], r['ret']), axis=1)
            all_cands.append(sub[[
                'symbol', 'da', 'bar_idx', 'bucket',
                'atr_pct', 'range_pct', 'ret', 'vol_ratio',
                'vol', 'avg_vol20', 'breakout', 'breakout_threshold',
                'prior_runup', 'recent_green',
                'op', 'hi', 'lo', 'cl', 'prev_close', 'bar_low',
            ] + [f'exit_cl_{h}' for h in HORIZONS]
              + [f'mfe_hi_{h}' for h in HORIZONS]
              + [f'mae_lo_{h}' for h in HORIZONS]])

    df_c = pd.concat(all_cands, ignore_index=True)
    df_c.rename(columns={'cl': 'entry_l1'}, inplace=True)
    df_c['entry_l15'] = df_c['prev_close'] * (1 + UNI_RET_MIN)  # Layer 1.5 approx
    print(f"  Candidates: {len(df_c)}  Baseline={len(df_c[df_c.bucket=='Baseline'])}  A={len(df_c[df_c.bucket=='A'])}  B={len(df_c[df_c.bucket=='B'])}  C={len(df_c[df_c.bucket=='C'])}  {time.time()-t0:.1f}s")

    # ---- Sanity check: SOLVUSDT 2026-04-29 17:00 ----
    print("\n--- Sanity check: SOLVUSDT 2026-04-29 17:00 ---")
    solv = df_c[(df_c['symbol'] == 'SOLVUSDT') & (df_c['da'] == pd.Timestamp('2026-04-29 17:00:00'))]
    sanity_pass = True
    if len(solv) == 0:
        print("  [FAIL] SOLVUSDT 2026-04-29 17:00 NOT in candidates")
        sanity_pass = False
    else:
        row = solv.iloc[0]
        checks = {
            'bucket_C': row['bucket'] == 'C',
            'ret_ok': abs(row['ret'] - 0.09897) <= SANITY_RET_TOL,
            'range_ok': abs(row['range_pct'] - 0.05843) <= SANITY_RANGE_TOL,
            'vol_ratio_ok': abs(row['vol_ratio'] - 77.0) / 77.0 <= SANITY_VOL_RATIO_REL_TOL,
            'breakout_ok': row['breakout'] is True or row['breakout'] == True,
            'future4_ok': not pd.isna(row.get('exit_cl_4', np.nan)),
        }
        for k, v in checks.items():
            status = "[PASS]" if v else "[FAIL]"
            print(f"  {status} {k}  actual: ret={row['ret']:.5f} range={row['range_pct']:.5f} vol_ratio={row['vol_ratio']:.1f} bucket={row['bucket']} future4={row.get('exit_cl_4')}")
            if not v:
                sanity_pass = False

    if not sanity_pass:
        print("\n[BLOCKED] Sanity check failed — stopping, no strategy conclusion.")
        sys.exit(3)
    print("  [OK] All sanity checks passed")

    # ---- Random sample for audit ----
    sample_ids = df_c.sample(min(8, len(df_c)), random_state=42)[['symbol', 'da', 'bucket']].copy()
    sample_ids.to_csv(REPORT_DIR / f"aggressive_backtest_sanity_samples_20260430.csv", index=False)
    print(f"  Sanity sample CSV: {REPORT_DIR}/aggressive_backtest_sanity_samples_20260430.csv")

    # ---- Layer 1 stats ----
    print("\n--- Layer 1 (finalized close entry) ---")
    stats_l1 = {}
    for h in HORIZONS:
        stats_l1[h] = _bucket_stats(df_c, 'entry_l1', h)
    for h in HORIZONS:
        for bkt in ['Baseline', 'A', 'B', 'C']:
            s = stats_l1[h][bkt]
            if s['N'] > 0:
                print(f"  L1 {bkt} {h}bar: N={s['N']} exp={s['expectancy']*100:.2f}% median={s['median_ret']*100:.2f}% sharpe={s['sharpe']:.2f}")

    # ---- Layer 1.5 stats ----
    print("\n--- Layer 1.5 (prev_close*1.017 entry) ---")
    stats_l15 = {}
    for h in HORIZONS:
        stats_l15[h] = _bucket_stats(df_c, 'entry_l15', h)
    for h in HORIZONS:
        for bkt in ['Baseline', 'A', 'B', 'C']:
            s = stats_l15[h][bkt]
            if s['N'] > 0:
                print(f"  L1.5 {bkt} {h}bar: N={s['N']} exp={s['expectancy']*100:.2f}% median={s['median_ret']*100:.2f}% sharpe={s['sharpe']:.2f}")

    # ---- Layer 2: load 3m, compute trigger bars ----
    print(f"\n--- Layer 2 (3m in-progress) ---  {time.time()-t0:.1f}s")
    # Load 3m for all symbols that have candidates
    cand_symbols = df_c['symbol'].unique().tolist()
    print(f"  Loading 3m for {len(cand_symbols)} symbols...")
    _, rows3 = _query_all(
        f"SELECT code, da, op, hi, lo, cl, vol FROM {TABLES['3m']} "
        f"WHERE code = ANY(%s) ORDER BY code, da",
        (cand_symbols,)
    )
    df3 = pd.DataFrame(rows3, columns=['code', 'da', 'op', 'hi', 'lo', 'cl', 'vol'])
    df3[['op', 'hi', 'lo', 'cl', 'vol']] = df3[['op', 'hi', 'lo', 'cl', 'vol']].astype(float)
    df3['da'] = pd.to_datetime(df3['da'])
    print(f"  3m rows: {len(df3):,}  {time.time()-t0:.1f}s")

    # Index 3m by symbol
    df3_by_sym = {sym: grp.sort_values('da').reset_index(drop=True) for sym, grp in df3.groupby('code')}

    # For each candidate, find first 3m trigger bar
    layer2_rows = []
    INTERVAL_3M_DELTA = timedelta(minutes=3)
    INTERVAL_15M_DELTA = timedelta(minutes=15)

    for _, cand in df_c.iterrows():
        sym = cand['symbol']
        bar_da = cand['da']  # naive datetime = UTC+8 wall-clock
        prev_cl = float(cand['prev_close'])
        avg_vol20 = float(cand['avg_vol20'])
        breakout_threshold = float(cand['breakout_threshold'])
        ret_trigger_price = prev_cl * (1 + UNI_RET_MIN)

        if sym not in df3_by_sym:
            continue
        df3s = df3_by_sym[sym]
        trigger_found_opt = False
        trigger_found_con = False
        opt_row = None
        con_row = None
        cum_vol = 0.0
        cum_hi = -np.inf
        cum_lo = np.inf

        # 5 sub-3m bars in this 15m bar: bar_da, bar_da+3m, +6m, +9m, +12m.
        # At each step, reconstruct the in-progress 15m bar from cumulative 3m data.
        bar_end = bar_da + INTERVAL_15M_DELTA - INTERVAL_3M_DELTA  # last sub-bar open
        sub3 = df3s[(df3s['da'] >= bar_da) & (df3s['da'] <= bar_end)]

        for j, r3 in sub3.iterrows():
            cum_vol += float(r3['vol'])
            cum_hi = max(cum_hi, float(r3['hi']))
            cum_lo = min(cum_lo, float(r3['lo']))

            ret_close = (float(r3['cl']) - prev_cl) / prev_cl if prev_cl > 0 else 0.0
            ret_high = (cum_hi - prev_cl) / prev_cl if prev_cl > 0 else 0.0
            volume_ratio_at_trigger = cum_vol / avg_vol20 if avg_vol20 > 0 else 0.0
            volume_ok = volume_ratio_at_trigger >= UNI_VOL_RATIO_MIN
            breakout_ok = cum_hi > breakout_threshold

            # Conservative trigger matches SignalEngine's close-based return check
            # at the 3m sampling boundary, plus cumulative volume and breakout.
            if (
                not trigger_found_con
                and volume_ok
                and breakout_ok
                and ret_close >= UNI_RET_MIN
            ):
                trigger_found_con = True
                con_row = {
                    'trigger_da': r3['da'],
                    'trigger_offset_min': int((r3['da'] - bar_da).total_seconds() // 60),
                    'entry_price': float(r3['cl']),
                    'stop_reference': float(cum_lo),
                    'entry_mode': 'conservative',
                    'ret_at_trigger': float(ret_close),
                    'volume_ratio_at_trigger': float(volume_ratio_at_trigger),
                    'cum_volume_at_trigger': float(cum_vol),
                    'cum_high_at_trigger': float(cum_hi),
                    'breakout_threshold': float(breakout_threshold),
                    'breakout_at_trigger': bool(breakout_ok),
                }

            # Optimistic high-touch trigger is an upper-bound approximation.
            if (
                not trigger_found_opt
                and volume_ok
                and breakout_ok
                and ret_high >= UNI_RET_MIN
            ):
                trigger_found_opt = True
                threshold_price = max(ret_trigger_price, breakout_threshold)
                opt_row = {
                    'trigger_da': r3['da'],
                    'trigger_offset_min': int((r3['da'] - bar_da).total_seconds() // 60),
                    'entry_price': float(threshold_price),
                    'stop_reference': float(cum_lo),
                    'entry_mode': 'optimistic',
                    'ret_at_trigger': float(ret_high),
                    'volume_ratio_at_trigger': float(volume_ratio_at_trigger),
                    'cum_volume_at_trigger': float(cum_vol),
                    'cum_high_at_trigger': float(cum_hi),
                    'breakout_threshold': float(breakout_threshold),
                    'breakout_at_trigger': bool(breakout_ok),
                }

        base_row = {
            'symbol': sym,
            'bar_da': bar_da,
            'bucket': cand['bucket'],
            'atr_pct': cand['atr_pct'],
            'range_pct': cand['range_pct'],
            'ret': cand['ret'],
            'vol_ratio': cand['vol_ratio'],
            'vol': cand['vol'],
            'avg_vol20': cand['avg_vol20'],
            'breakout': cand['breakout'],
            'breakout_threshold': cand['breakout_threshold'],
            'prior_runup': cand['prior_runup'],
            'recent_green': cand['recent_green'],
            'layer': 'L2',
        }
        base_row.update({f'exit_cl_{h}': cand[f'exit_cl_{h}'] for h in HORIZONS})
        base_row.update({f'mfe_hi_{h}': cand[f'mfe_hi_{h}'] for h in HORIZONS})
        base_row.update({f'mae_lo_{h}': cand[f'mae_lo_{h}'] for h in HORIZONS})
        base_row['bar_low'] = cand['bar_low']

        for trow in [opt_row, con_row]:
            if trow is not None:
                r = {**base_row, **trow, 'entry_l2': trow['entry_price']}
                layer2_rows.append(r)

    df_l2 = pd.DataFrame(layer2_rows)
    print(f"  Layer 2 rows: {len(df_l2)}  {time.time()-t0:.1f}s")

    # Layer 2 stats
    stats_l2_opt = {}
    stats_l2_con = {}
    if len(df_l2) > 0:
        df_l2_opt = df_l2[df_l2['entry_mode'] == 'optimistic'].copy()
        df_l2_con = df_l2[df_l2['entry_mode'] == 'conservative'].copy()
        for h in HORIZONS:
            stats_l2_opt[h] = _bucket_stats(df_l2_opt, 'entry_l2', h)
            stats_l2_con[h] = _bucket_stats(df_l2_con, 'entry_l2', h)
        print("  Layer 2 optimistic:")
        for h in HORIZONS:
            for bkt in ['Baseline', 'A', 'B', 'C']:
                s = stats_l2_opt[h].get(bkt, {})
                if s.get('N', 0) > 0:
                    print(f"    L2-opt {bkt} {h}bar: N={s['N']} exp={s['expectancy']*100:.2f}% median={s['median_ret']*100:.2f}% false_stop_ref={s['false_stop_reference_rate']*100:.1f}%")
        print("  Layer 2 conservative:")
        for h in HORIZONS:
            for bkt in ['Baseline', 'A', 'B', 'C']:
                s = stats_l2_con[h].get(bkt, {})
                if s.get('N', 0) > 0:
                    print(f"    L2-con {bkt} {h}bar: N={s['N']} exp={s['expectancy']*100:.2f}% median={s['median_ret']*100:.2f}% false_stop_ref={s['false_stop_reference_rate']*100:.1f}%")

    # Save cache
    results = {
        'stats_l1': stats_l1,
        'stats_l15': stats_l15,
        'stats_l2_opt': stats_l2_opt,
        'stats_l2_con': stats_l2_con,
        'candidates_count': len(df_c),
    }
    with open(CACHE_DIR / "phase3_6_results.pkl", "wb") as f:
        pickle.dump({'results': results, 'df_c': df_c, 'df_l2': df_l2}, f)
    print(f"\n=> cache saved  total {time.time()-t0:.1f}s")

    # ---- Build candidate CSV ----
    csv_path = REPORT_DIR / "aggressive_backtest_candidates_20260430.csv"
    # Layer 1 rows
    l1_rows = df_c.copy()
    l1_rows['layer'] = 'L1'
    l1_rows['entry_mode'] = 'close'
    l1_rows['trigger_3m_open_time'] = None
    l1_rows['trigger_offset_in_bar_minutes'] = None
    l1_rows['entry_price'] = l1_rows['entry_l1']
    l1_rows['stop_reference'] = l1_rows['bar_low']

    # Layer 1.5 rows
    l15_rows = df_c.copy()
    l15_rows['layer'] = 'L1.5'
    l15_rows['entry_mode'] = 'optimistic_approx'
    l15_rows['trigger_3m_open_time'] = None
    l15_rows['trigger_offset_in_bar_minutes'] = None
    l15_rows['entry_price'] = l15_rows['entry_l15']
    l15_rows['stop_reference'] = l15_rows['bar_low']

    for h in HORIZONS:
        for df_layer, entry_col in [(l1_rows, 'entry_price'), (l15_rows, 'entry_price')]:
            df_layer[f'return_after_cost_{h}'] = (df_layer[f'exit_cl_{h}'] - df_layer[entry_col]) / df_layer[entry_col] - COST_TOTAL_PCT
            df_layer[f'mfe_pct_{h}'] = (df_layer[f'mfe_hi_{h}'] - df_layer[entry_col]) / df_layer[entry_col]
            df_layer[f'mae_pct_{h}'] = (df_layer[f'mae_lo_{h}'] - df_layer[entry_col]) / df_layer[entry_col]
            df_layer[f'stop_hit_3pct_{h}'] = df_layer[f'mae_lo_{h}'] <= df_layer[entry_col] * 0.97
            df_layer[f'stop_hit_5pct_{h}'] = df_layer[f'mae_lo_{h}'] <= df_layer[entry_col] * 0.95
            df_layer[f'stop_hit_bar_low_{h}'] = df_layer[f'mae_lo_{h}'] <= df_layer['bar_low']
            df_layer[f'stop_hit_stop_reference_{h}'] = df_layer[f'mae_lo_{h}'] <= df_layer['stop_reference']
            df_layer[f'false_stop_3pct_{h}'] = df_layer[f'stop_hit_3pct_{h}'] & (df_layer[f'exit_cl_{h}'] > df_layer[entry_col] * 0.97)
            df_layer[f'false_stop_reference_{h}'] = df_layer[f'stop_hit_stop_reference_{h}'] & (df_layer[f'exit_cl_{h}'] > df_layer['stop_reference'])

    base_cols = ['symbol', 'da', 'bucket', 'atr_pct', 'range_pct', 'ret', 'vol_ratio',
                 'vol', 'avg_vol20', 'breakout', 'breakout_threshold',
                 'prior_runup', 'recent_green', 'layer', 'entry_mode',
                 'trigger_3m_open_time', 'trigger_offset_in_bar_minutes',
                 'entry_price', 'stop_reference', 'bar_low',
                 'volume_ratio_at_trigger', 'cum_volume_at_trigger',
                 'cum_high_at_trigger', 'breakout_at_trigger']
    for h in HORIZONS:
        base_cols += [f'exit_cl_{h}', f'return_after_cost_{h}', f'mfe_pct_{h}', f'mae_pct_{h}',
                      f'stop_hit_3pct_{h}', f'stop_hit_5pct_{h}', f'stop_hit_bar_low_{h}',
                      f'stop_hit_stop_reference_{h}', f'false_stop_3pct_{h}', f'false_stop_reference_{h}']

    # Combine
    csv_frames = [l1_rows, l15_rows]
    if len(df_l2) > 0:
        df_l2['layer'] = 'L2'
        df_l2['da'] = df_l2['bar_da']
        df_l2['trigger_3m_open_time'] = df_l2['trigger_da'].astype(str) if 'trigger_da' in df_l2.columns else None
        df_l2['trigger_offset_in_bar_minutes'] = df_l2['trigger_offset_min'] if 'trigger_offset_min' in df_l2.columns else None
        df_l2['entry_price'] = df_l2['entry_l2']
        df_l2['stop_reference'] = df_l2['stop_reference'] if 'stop_reference' in df_l2.columns else None
        for h in HORIZONS:
            if f'exit_cl_{h}' in df_l2.columns:
                df_l2[f'return_after_cost_{h}'] = (df_l2[f'exit_cl_{h}'] - df_l2['entry_l2']) / df_l2['entry_l2'] - COST_TOTAL_PCT
                df_l2[f'mfe_pct_{h}'] = (df_l2[f'mfe_hi_{h}'] - df_l2['entry_l2']) / df_l2['entry_l2']
                df_l2[f'mae_pct_{h}'] = (df_l2[f'mae_lo_{h}'] - df_l2['entry_l2']) / df_l2['entry_l2']
                df_l2[f'stop_hit_3pct_{h}'] = df_l2[f'mae_lo_{h}'] <= df_l2['entry_l2'] * 0.97
                df_l2[f'stop_hit_5pct_{h}'] = df_l2[f'mae_lo_{h}'] <= df_l2['entry_l2'] * 0.95
                df_l2[f'stop_hit_bar_low_{h}'] = df_l2[f'mae_lo_{h}'] <= df_l2['bar_low']
                df_l2[f'stop_hit_stop_reference_{h}'] = df_l2[f'mae_lo_{h}'] <= df_l2['stop_reference']
                df_l2[f'false_stop_3pct_{h}'] = df_l2[f'stop_hit_3pct_{h}'] & (df_l2[f'exit_cl_{h}'] > df_l2['entry_l2'] * 0.97)
                df_l2[f'false_stop_reference_{h}'] = df_l2[f'stop_hit_stop_reference_{h}'] & (df_l2[f'exit_cl_{h}'] > df_l2['stop_reference'])
        csv_frames.append(df_l2)

    df_csv = pd.concat(csv_frames, ignore_index=True)
    available_cols = [c for c in base_cols if c in df_csv.columns]
    df_csv[available_cols].to_csv(csv_path, index=False)
    print(f"=> CSV: {csv_path}  ({len(df_csv)} rows)")

    # Save all results for report generation
    with open(CACHE_DIR / "audit_final.pkl", "wb") as f:
        pickle.dump({
            'stats_l1': stats_l1, 'stats_l15': stats_l15,
            'stats_l2_opt': stats_l2_opt, 'stats_l2_con': stats_l2_con,
            'n_cands': len(df_c),
        }, f)

    elapsed = time.time() - t0
    print(f"\n=== audit done in {elapsed:.0f}s ===")
    return results


def cmd_audit_live_safe(args):
    """Low-memory audit path for running while the live bot remains active."""
    import pandas as pd

    if args.batch_size <= 0:
        print("[ERR] --batch-size must be > 0")
        sys.exit(2)
    if args.sleep_seconds < 0:
        print("[ERR] --sleep-seconds must be >= 0")
        sys.exit(2)

    run_id = args.run_id or datetime.now(timezone.utc).strftime("live_safe_%Y%m%d_%H%M%S")
    out_dir = CACHE_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    progress_path = out_dir / "progress.json"

    print(f"=== Phase 3-6 audit-live-safe @ {_now_utc().isoformat()} run_id={run_id} ===")
    print(f"  batch_size={args.batch_size} sleep_seconds={args.sleep_seconds}")
    print("  read-only DB path; no backfill; no private/account/order API")
    t0 = time.time()

    _, rows = _query_all(f"SELECT DISTINCT code FROM {TABLES['15m']} ORDER BY code;")
    symbols = [r[0] for r in rows]
    if args.max_symbols is not None:
        symbols = symbols[:args.max_symbols]
        print(f"  [LIMIT] max_symbols={args.max_symbols}")
    print(f"  symbols={len(symbols)}")

    candidate_frames = []
    layer2_frames = []
    processed = 0
    total_batches = (len(symbols) + args.batch_size - 1) // args.batch_size

    for batch_idx, batch_symbols in _batched(symbols, args.batch_size):
        batch_no = batch_idx // args.batch_size + 1
        print(f"\n--- batch {batch_no}/{total_batches} symbols={len(batch_symbols)} elapsed={time.time()-t0:.1f}s ---")

        _, rows15 = _query_all(
            f"SELECT code, da, op, hi, lo, cl, vol FROM {TABLES['15m']} "
            f"WHERE code = ANY(%s) ORDER BY code, da",
            (batch_symbols,),
        )
        df15 = pd.DataFrame(rows15, columns=['code', 'da', 'op', 'hi', 'lo', 'cl', 'vol'])
        if len(df15) == 0:
            processed += len(batch_symbols)
            continue
        df15[['op', 'hi', 'lo', 'cl', 'vol']] = df15[['op', 'hi', 'lo', 'cl', 'vol']].astype(float)
        df_c_batch = _build_candidates_from_15m(df15)

        df_l2_batch = pd.DataFrame()
        if len(df_c_batch) > 0:
            cand_symbols = df_c_batch['symbol'].dropna().unique().tolist()
            _, rows3 = _query_all(
                f"SELECT code, da, op, hi, lo, cl, vol FROM {TABLES['3m']} "
                f"WHERE code = ANY(%s) ORDER BY code, da",
                (cand_symbols,),
            )
            df3 = pd.DataFrame(rows3, columns=['code', 'da', 'op', 'hi', 'lo', 'cl', 'vol'])
            if len(df3) > 0:
                df3[['op', 'hi', 'lo', 'cl', 'vol']] = df3[['op', 'hi', 'lo', 'cl', 'vol']].astype(float)
                df3['da'] = pd.to_datetime(df3['da'])
                df_l2_batch = _build_layer2_from_candidates(df_c_batch, df3)

        if len(df_c_batch) > 0:
            candidate_frames.append(df_c_batch)
        if len(df_l2_batch) > 0:
            layer2_frames.append(df_l2_batch)

        processed += len(batch_symbols)
        progress = {
            "run_id": run_id,
            "updated_at": _now_utc().isoformat(),
            "processed_symbols": processed,
            "total_symbols": len(symbols),
            "batch_no": batch_no,
            "total_batches": total_batches,
            "candidate_rows": int(sum(len(x) for x in candidate_frames)),
            "layer2_rows": int(sum(len(x) for x in layer2_frames)),
            "elapsed_seconds": round(time.time() - t0, 1),
        }
        progress_path.write_text(json.dumps(progress, indent=2, default=str))
        print(f"  batch candidates={len(df_c_batch)} l2={len(df_l2_batch)} total_candidates={progress['candidate_rows']} total_l2={progress['layer2_rows']}")

        del df15, df_c_batch, df_l2_batch
        if 'df3' in locals():
            del df3
        gc.collect()
        if args.sleep_seconds and batch_no < total_batches:
            time.sleep(args.sleep_seconds)

    if candidate_frames:
        df_c = pd.concat(candidate_frames, ignore_index=True)
    else:
        print("[BLOCKED] no candidates generated")
        sys.exit(3)
    df_l2 = pd.concat(layer2_frames, ignore_index=True) if layer2_frames else pd.DataFrame()

    stats_l1, stats_l15, stats_l2_opt, stats_l2_con = _compute_audit_stats(df_c, df_l2)
    results = {
        "stats_l1": stats_l1,
        "stats_l15": stats_l15,
        "stats_l2_opt": stats_l2_opt,
        "stats_l2_con": stats_l2_con,
        "candidates_count": int(len(df_c)),
        "layer2_rows_count": int(len(df_l2)),
        "run_id": run_id,
        "batch_size": args.batch_size,
        "sleep_seconds": args.sleep_seconds,
        "max_symbols": args.max_symbols,
    }

    print("\n--- live-safe summary ---")
    print(f"  candidates={len(df_c)} layer2_rows={len(df_l2)} elapsed={time.time()-t0:.1f}s")
    _print_layer_summary("Layer 1", stats_l1)
    _print_layer_summary("Layer 1.5", stats_l15)
    _print_layer_summary("Layer 2 optimistic", stats_l2_opt)
    _print_layer_summary("Layer 2 conservative", stats_l2_con)

    c_path = out_dir / f"candidates_15m_{run_id}.csv"
    l2_path = out_dir / f"layer2_{run_id}.csv"
    json_path = out_dir / f"results_{run_id}.json"
    pkl_path = out_dir / f"results_{run_id}.pkl"
    df_c.to_csv(c_path, index=False)
    df_l2.to_csv(l2_path, index=False)
    json_path.write_text(json.dumps(results, indent=2, default=str))
    with open(pkl_path, "wb") as f:
        pickle.dump({"results": results, "df_c": df_c, "df_l2": df_l2}, f)

    print(f"=> {c_path}")
    print(f"=> {l2_path}")
    print(f"=> {json_path}")
    print(f"=> {pkl_path}")
    print(f"=== audit-live-safe done in {time.time()-t0:.0f}s ===")
    return results


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inventory")
    p2 = sub.add_parser("dryrun")
    p2.add_argument("--days-15m", type=int, default=365)
    p2.add_argument("--days-3m", type=int, default=120)
    p2.add_argument("--forward-only", action="store_true", help="skip backward fill, only fill forward to now")
    sub.add_parser("backfill")
    sub.add_parser("audit")
    p_safe = sub.add_parser("audit-live-safe")
    p_safe.add_argument("--batch-size", type=int, default=5, help="number of symbols per DB batch")
    p_safe.add_argument("--sleep-seconds", type=float, default=1.0, help="pause between batches to reduce live contention")
    p_safe.add_argument("--max-symbols", type=int, default=None, help="optional smoke-test symbol cap")
    p_safe.add_argument("--run-id", default=None, help="output directory name under reports/cache_<date>/")
    args = p.parse_args()
    if args.cmd == "inventory":
        cmd_inventory(args)
    elif args.cmd == "dryrun":
        cmd_dryrun(args)
    elif args.cmd == "backfill":
        cmd_backfill(args)
    elif args.cmd == "audit":
        cmd_audit(args)
    elif args.cmd == "audit-live-safe":
        cmd_audit_live_safe(args)


if __name__ == "__main__":
    main()
