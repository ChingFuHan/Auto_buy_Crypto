from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SUPPORTED_STRATEGY_INTERVALS = {"3m", "15m"}


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None or value == "" else int(value)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value is None or value == "" else float(value)


def _env_decimal(name: str, default: str) -> Decimal:
    value = os.getenv(name)
    return Decimal(default if value is None or value == "" else value)


def _env_csv(name: str, default: str = "") -> tuple[str, ...]:
    raw = os.getenv(name, default)
    if not raw:
        return tuple()
    return tuple(item.strip().upper() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int
    backoff_base_seconds: float
    backoff_max_seconds: float


@dataclass(frozen=True)
class StrategyConfig:
    interval: str
    lookback: int
    breakout_lookback: int
    atr_pct_max: Decimal
    range_pct_max: Decimal
    volume_multiple: Decimal
    return_pct_min: Decimal
    prior_runup_limit_pct: Decimal
    overheat_limit_pct: Decimal
    max_recent_green_bars: int


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    log_dir: Path
    data_dir: Path
    fallback_csv_path: Path
    staging_1m_csv_path: Path
    staging_3m_csv_path: Path
    api_key: str
    api_secret: str
    testnet: bool
    enable_live_trading: bool
    function_test_mode: bool
    function_test_symbol: str
    telegram_enabled: bool
    telegram_bot_token: str
    telegram_chat_id: str
    db_name: str
    position_sizing_mode: str
    target_notional_usdt: Decimal
    max_concurrent_positions: int
    stop_order_retry_count: int
    stop_working_type: str
    stop_price_mode: str
    stop_notional_risk_pct: Decimal
    server_time_sync_enabled: bool
    server_time_resync_interval_seconds: int
    max_server_time_offset_ms: int
    recv_window: int
    retry: RetryConfig
    strategy: StrategyConfig
    backfill_days: int
    backfill_limit: int
    backfill_concurrency: int
    startup_backfill_enabled: bool
    kline_seed_limit: int
    symbol_refresh_interval_seconds: int
    position_refresh_interval_seconds: int
    account_snapshot_max_age_seconds: float
    fallback_poll_interval_seconds: int
    staging_flush_interval_seconds: int
    signal_audit_maintenance_enabled: bool
    signal_audit_archive_after_days: int
    signal_audit_retention_days: int
    signal_audit_maintenance_interval_seconds: int
    signal_audit_archive_format: str
    signal_audit_gzip_compresslevel: int
    ws_max_streams_per_connection: int
    ws_max_reconnect_attempts: int
    heartbeat_enabled: bool
    heartbeat_interval_seconds: int
    symbol_blacklist: tuple[str, ...]
    symbol_whitelist: tuple[str, ...]
    excluded_big_caps: tuple[str, ...]
    log_level: str
    rest_base_url_override: str | None
    ws_base_url_override: str | None

    @property
    def rest_base_url(self) -> str:
        if self.rest_base_url_override:
            return self.rest_base_url_override
        if self.testnet:
            return "https://testnet.binancefuture.com"
        return "https://fapi.binance.com"

    @property
    def ws_base_url(self) -> str:
        if self.ws_base_url_override:
            return self.ws_base_url_override
        if self.testnet:
            return "wss://stream.binancefuture.com"
        return "wss://fstream.binance.com/market"

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_enabled and self.telegram_bot_token and self.telegram_chat_id)

    @property
    def strategy_interval(self) -> str:
        return self.strategy.interval

    @property
    def strategy_table_name(self) -> str:
        return f"public.semi_auto_price_future_{self.strategy_interval}"

    @property
    def strategy_staging_csv_path(self) -> Path:
        return self.data_dir / f"inprogress_{self.strategy_interval}.csv"

    @property
    def strategy_interval_ms(self) -> int:
        return _interval_to_milliseconds(self.strategy_interval)


def _interval_to_milliseconds(interval: str) -> int:
    if not interval.endswith("m"):
        raise ValueError(f"Unsupported minute interval: {interval}")
    return int(interval[:-1]) * 60_000


def _signal_env_name(interval: str, suffix: str) -> str:
    return f"SIGNAL_{interval.upper()}_{suffix}"


def _load_strategy_config(interval: str) -> StrategyConfig:
    defaults = {
        "3m": {
            "lookback": 20,
            "breakout_lookback": 12,
            "atr_pct_max": "0.015",
            "range_pct_max": "0.035",
            "volume_multiple": "2.0",
            "return_pct_min": "0.017",
            "overheat_limit_pct": "0.060",
        },
        "15m": {
            "lookback": 20,
            "breakout_lookback": 12,
            "atr_pct_max": "0.015",
            "range_pct_max": "0.035",
            "volume_multiple": "2.0",
            "return_pct_min": "0.017",
            "overheat_limit_pct": "0.060",
        },
    }[interval]
    return StrategyConfig(
        interval=interval,
        lookback=_env_int(_signal_env_name(interval, "LOOKBACK"), defaults["lookback"]),
        breakout_lookback=_env_int(_signal_env_name(interval, "BREAKOUT_LOOKBACK"), defaults["breakout_lookback"]),
        atr_pct_max=_env_decimal(_signal_env_name(interval, "COMPRESSION_ATR_PCT_MAX"), defaults["atr_pct_max"]),
        range_pct_max=_env_decimal(_signal_env_name(interval, "COMPRESSION_RANGE_PCT_MAX"), defaults["range_pct_max"]),
        volume_multiple=_env_decimal(_signal_env_name(interval, "VOLUME_MULTIPLE"), defaults["volume_multiple"]),
        return_pct_min=_env_decimal(_signal_env_name(interval, "RETURN_PCT_MIN"), defaults["return_pct_min"]),
        prior_runup_limit_pct=_env_decimal("SIGNAL_PRIOR_RUNUP_LIMIT_PCT", "0.040"),
        overheat_limit_pct=_env_decimal(_signal_env_name(interval, "OVERHEAT_LIMIT_PCT"), defaults["overheat_limit_pct"]),
        max_recent_green_bars=_env_int("SIGNAL_MAX_RECENT_GREEN_BARS", 3),
    )


def load_settings() -> Settings:
    strategy_interval = os.getenv("STRATEGY_INTERVAL", "15m").strip().lower()
    if strategy_interval not in SUPPORTED_STRATEGY_INTERVALS:
        raise ValueError("STRATEGY_INTERVAL must be 3m or 15m")
    position_sizing_mode = os.getenv("POSITION_SIZING_MODE", "FIXED_NOTIONAL").strip().upper()
    if position_sizing_mode not in {"FIXED_NOTIONAL", "BALANCE_SPLIT"}:
        raise ValueError("POSITION_SIZING_MODE must be FIXED_NOTIONAL or BALANCE_SPLIT")
    max_concurrent_positions = _env_int("MAX_CONCURRENT_POSITIONS", 3)
    if max_concurrent_positions < 1:
        raise ValueError("MAX_CONCURRENT_POSITIONS must be greater than or equal to 1")
    stop_working_type = os.getenv("STOP_WORKING_TYPE", "CONTRACT_PRICE").strip().upper()
    if stop_working_type not in {"CONTRACT_PRICE", "MARK_PRICE"}:
        raise ValueError("STOP_WORKING_TYPE must be CONTRACT_PRICE or MARK_PRICE")
    stop_price_mode = os.getenv("STOP_PRICE_MODE", "IN_PROGRESS_3M_LOW").strip().upper()
    if stop_price_mode not in {"IN_PROGRESS_INTERVAL_LOW", "IN_PROGRESS_3M_LOW", "IN_PROGRESS_15M_LOW", "NOTIONAL_RISK_PCT"}:
        raise ValueError("STOP_PRICE_MODE must be IN_PROGRESS_INTERVAL_LOW, IN_PROGRESS_3M_LOW, IN_PROGRESS_15M_LOW, or NOTIONAL_RISK_PCT")
    stop_notional_risk_pct = _env_decimal("STOP_NOTIONAL_RISK_PCT", "0.50")
    if stop_notional_risk_pct <= Decimal("0") or stop_notional_risk_pct >= Decimal("1"):
        raise ValueError("STOP_NOTIONAL_RISK_PCT must be greater than 0 and less than 1")
    heartbeat_interval_seconds = _env_int("HEARTBEAT_INTERVAL_SECONDS", 900)
    if heartbeat_interval_seconds < 60:
        raise ValueError("HEARTBEAT_INTERVAL_SECONDS must be at least 60")
    signal_audit_archive_after_days = _env_int("SIGNAL_AUDIT_ARCHIVE_AFTER_DAYS", 1)
    if signal_audit_archive_after_days < 1:
        raise ValueError("SIGNAL_AUDIT_ARCHIVE_AFTER_DAYS must be at least 1")
    signal_audit_retention_days = _env_int("SIGNAL_AUDIT_RETENTION_DAYS", 7)
    if signal_audit_retention_days < 0:
        raise ValueError("SIGNAL_AUDIT_RETENTION_DAYS must be greater than or equal to 0")
    signal_audit_maintenance_interval_seconds = _env_int("SIGNAL_AUDIT_MAINTENANCE_INTERVAL_SECONDS", 3600)
    if signal_audit_maintenance_interval_seconds < 60:
        raise ValueError("SIGNAL_AUDIT_MAINTENANCE_INTERVAL_SECONDS must be at least 60")
    signal_audit_archive_format = os.getenv("SIGNAL_AUDIT_ARCHIVE_FORMAT", "gzip").strip().lower()
    if signal_audit_archive_format not in {"gzip", "parquet"}:
        raise ValueError("SIGNAL_AUDIT_ARCHIVE_FORMAT must be gzip or parquet")
    signal_audit_gzip_compresslevel = _env_int("SIGNAL_AUDIT_GZIP_COMPRESSLEVEL", 6)
    if signal_audit_gzip_compresslevel < 1 or signal_audit_gzip_compresslevel > 9:
        raise ValueError("SIGNAL_AUDIT_GZIP_COMPRESSLEVEL must be between 1 and 9")

    return Settings(
        base_dir=BASE_DIR,
        log_dir=BASE_DIR / "logs",
        data_dir=BASE_DIR / "data",
        fallback_csv_path=BASE_DIR / "data" / "fallback_stop_state.csv",
        staging_1m_csv_path=BASE_DIR / "data" / "inprogress_1m.csv",
        staging_3m_csv_path=BASE_DIR / "data" / "inprogress_3m.csv",
        api_key=os.getenv("API_KEY", ""),
        api_secret=os.getenv("API_SECRET", ""),
        testnet=_env_bool("TESTNET", True),
        enable_live_trading=_env_bool("ENABLE_LIVE_TRADING", False),
        function_test_mode=_env_bool("FUNCTION_TEST_MODE", True),
        function_test_symbol=os.getenv("FUNCTION_TEST_SYMBOL", "BTCUSDT").strip().upper(),
        telegram_enabled=_env_bool("TELEGRAM_ENABLED", True),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        db_name=os.getenv("DB_NAME", "daily"),
        position_sizing_mode=position_sizing_mode,
        target_notional_usdt=_env_decimal("TARGET_NOTIONAL_USDT", "300"),
        max_concurrent_positions=max_concurrent_positions,
        stop_order_retry_count=_env_int("STOP_ORDER_RETRY_COUNT", 3),
        stop_working_type=stop_working_type,
        stop_price_mode=stop_price_mode,
        stop_notional_risk_pct=stop_notional_risk_pct,
        server_time_sync_enabled=_env_bool("SERVER_TIME_SYNC_ENABLED", True),
        server_time_resync_interval_seconds=_env_int("SERVER_TIME_RESYNC_INTERVAL_SECONDS", 60),
        max_server_time_offset_ms=_env_int("MAX_SERVER_TIME_OFFSET_MS", 5000),
        recv_window=_env_int("RECV_WINDOW", 10000),
        retry=RetryConfig(
            max_attempts=_env_int("API_RETRY_MAX_ATTEMPTS", 3),
            backoff_base_seconds=_env_float("API_RETRY_BACKOFF_BASE_SECONDS", 1.0),
            backoff_max_seconds=_env_float("API_RETRY_BACKOFF_MAX_SECONDS", 8.0),
        ),
        strategy=_load_strategy_config(strategy_interval),
        backfill_days=_env_int("BACKFILL_DAYS", 90),
        backfill_limit=_env_int("BACKFILL_LIMIT", 1000),
        backfill_concurrency=_env_int("BACKFILL_CONCURRENCY", 4),
        startup_backfill_enabled=_env_bool("STARTUP_BACKFILL_ENABLED", True),
        kline_seed_limit=_env_int("KLINE_SEED_LIMIT", 90),
        symbol_refresh_interval_seconds=_env_int("SYMBOL_REFRESH_INTERVAL_SECONDS", 900),
        position_refresh_interval_seconds=_env_int("POSITION_REFRESH_INTERVAL_SECONDS", 30),
        account_snapshot_max_age_seconds=_env_float("ACCOUNT_SNAPSHOT_MAX_AGE_SECONDS", 10.0),
        fallback_poll_interval_seconds=_env_int("FALLBACK_POLL_INTERVAL_SECONDS", 1),
        staging_flush_interval_seconds=_env_int("STAGING_FLUSH_INTERVAL_SECONDS", 1),
        signal_audit_maintenance_enabled=_env_bool("SIGNAL_AUDIT_MAINTENANCE_ENABLED", True),
        signal_audit_archive_after_days=signal_audit_archive_after_days,
        signal_audit_retention_days=signal_audit_retention_days,
        signal_audit_maintenance_interval_seconds=signal_audit_maintenance_interval_seconds,
        signal_audit_archive_format=signal_audit_archive_format,
        signal_audit_gzip_compresslevel=signal_audit_gzip_compresslevel,
        ws_max_streams_per_connection=_env_int("WS_MAX_STREAMS_PER_CONNECTION", 200),
        ws_max_reconnect_attempts=_env_int("WS_MAX_RECONNECT_ATTEMPTS", 3),
        heartbeat_enabled=_env_bool("HEARTBEAT_ENABLED", True),
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        symbol_blacklist=_env_csv("SYMBOL_BLACKLIST"),
        symbol_whitelist=_env_csv("SYMBOL_WHITELIST"),
        excluded_big_caps=_env_csv(
            "EXCLUDED_BIG_CAPS",
            "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,DOGEUSDT,ADAUSDT",
        ),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        rest_base_url_override=os.getenv("BINANCE_REST_BASE_URL") or None,
        ws_base_url_override=os.getenv("BINANCE_WS_BASE_URL") or None,
    )
