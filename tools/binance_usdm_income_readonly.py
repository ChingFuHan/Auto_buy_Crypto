"""Read-only Binance USD-M Futures income reporter.

This tool queries account income for COMMISSION and FUNDING_FEE only.
Dry-run is the default and does not send Binance requests.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx
from dotenv import dotenv_values


TAIPEI_TZ = ZoneInfo("Asia/Taipei")
BASE_URLS = {
    "https://fapi.binance.com": "binance_fapi_mainnet",
    "https://testnet.binancefuture.com": "binance_fapi_testnet",
}
ENDPOINT_TIME = "/fapi/v1/time"
ENDPOINT_INCOME = "/fapi/v1/income"
ALLOWED_ENDPOINTS = {ENDPOINT_TIME, ENDPOINT_INCOME}
INCOME_TYPES = ("COMMISSION", "FUNDING_FEE")
DEFAULT_DAYS = 10
MAX_LOOKBACK_DAYS = 90
INCOME_LIMIT = 1000
MAX_PAGES_PER_INCOME_TYPE = 50
INCOME_WEIGHT = 30
MAX_RETRY_ATTEMPTS = 3
OFFSET_BLOCK_MS = 30_000
DEFAULT_RECV_WINDOW = 5000
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = PROJECT_ROOT / "tools" / "outputs"


class BlockedError(RuntimeError):
    """Raised when a safety rule blocks execution."""


class BinanceRequestError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


@dataclass
class RunContext:
    mode: str
    will_send: bool
    base_url: str
    base_url_label: str
    days: int
    start_local: datetime
    end_local: datetime
    start_ms: int
    end_ms_exclusive: int
    end_ms_request: int
    output_report: Path
    request_count: int = 0
    partial: bool = False
    blocked_reason: str | None = None
    live_bot_warning: str | None = None
    offset_ms: int | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only Binance USD-M Futures income reporter."
    )
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--api-key-var", default="API_KEY")
    parser.add_argument("--api-secret-var", default="API_SECRET")
    parser.add_argument("--base-url", default="https://fapi.binance.com")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-readonly", action="store_true")
    parser.add_argument("--output-report")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    return parser.parse_args()


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


def short_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def resolve_base_url(raw: str) -> tuple[str, str]:
    base_url = raw.rstrip("/")
    if base_url not in BASE_URLS:
        raise BlockedError(f"base URL not allowlisted: {base_url}")
    return base_url, BASE_URLS[base_url]


def validate_days(days: int) -> int:
    if days <= 0:
        raise BlockedError("--days must be positive")
    if days > MAX_LOOKBACK_DAYS:
        raise BlockedError(
            f"--days exceeds the conservative {MAX_LOOKBACK_DAYS}-day income lookback limit"
        )
    return days


def epoch_ms(value: datetime) -> int:
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


def build_time_range(days: int) -> tuple[datetime, datetime, int, int, int]:
    end_local = datetime.now(TAIPEI_TZ)
    start_local = end_local - timedelta(days=days)
    start_ms = epoch_ms(start_local)
    end_ms_exclusive = epoch_ms(end_local)
    end_ms_request = end_ms_exclusive - 1
    return start_local, end_local, start_ms, end_ms_exclusive, end_ms_request


def default_report_path() -> Path:
    stamp = datetime.now(TAIPEI_TZ).strftime("%Y%m%d_%H%M%S")
    return OUTPUTS_DIR / f"income_report_{stamp}.md"


def resolve_output_path(raw_path: str | None) -> Path:
    output_path = Path(raw_path) if raw_path else default_report_path()
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    output_path = output_path.resolve()
    outputs_dir = OUTPUTS_DIR.resolve()
    try:
        allowed = output_path.is_relative_to(outputs_dir)
    except AttributeError:
        allowed = str(output_path).startswith(str(outputs_dir) + "/")
    if not allowed:
        raise BlockedError("output report must be under tools/outputs/")
    return output_path


def ensure_output_writable(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise BlockedError(f"output report exists; pass --overwrite to replace: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)


def load_env_values(env_file: str) -> dict[str, str]:
    env_path = Path(env_file)
    if not env_path.is_absolute():
        env_path = PROJECT_ROOT / env_path
    values = dotenv_values(env_path)
    return {key: value for key, value in values.items() if value is not None}


def resolve_credentials(
    values: dict[str, str], api_key_var: str, api_secret_var: str
) -> tuple[str, str]:
    api_key = values.get(api_key_var, "")
    api_secret = values.get(api_secret_var, "")
    if not api_key or not api_secret:
        raise BlockedError("API key or secret variable is missing from env file")
    return api_key, api_secret


def detect_live_bot() -> str | None:
    try:
        result = subprocess.run(
            ["pgrep", "-af", "main.py run"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    matches = []
    for line in result.stdout.splitlines():
        if "pgrep" in line:
            continue
        if "main.py" in line and "run" in line:
            matches.append(line)
    if matches:
        return "main.py run appears to be running"
    return None


def ensure_endpoint_allowed(endpoint: str) -> None:
    if endpoint not in ALLOWED_ENDPOINTS:
        raise BlockedError(f"endpoint not allowlisted: {endpoint}")


def parse_binance_error(response: httpx.Response) -> BinanceRequestError:
    code = None
    message = f"HTTP {response.status_code}"
    try:
        payload = response.json()
        if isinstance(payload, dict):
            code_value = payload.get("code")
            if isinstance(code_value, int):
                code = code_value
            message = str(payload.get("msg") or message)
    except json.JSONDecodeError:
        pass
    return BinanceRequestError(message, status_code=response.status_code, code=code)


def get_server_time(client: httpx.Client, base_url: str) -> tuple[int, int]:
    ensure_endpoint_allowed(ENDPOINT_TIME)
    local_before = int(time.time() * 1000)
    response = client.get(f"{base_url}{ENDPOINT_TIME}", timeout=10.0)
    local_after = int(time.time() * 1000)
    if response.status_code >= 400:
        raise parse_binance_error(response)
    payload = response.json()
    server_time = int(payload["serverTime"])
    local_midpoint = (local_before + local_after) // 2
    offset_ms = server_time - local_midpoint
    return server_time, offset_ms


def sign_params(params: dict[str, Any], api_secret: str) -> dict[str, Any]:
    encoded = urlencode(params, doseq=True)
    signature = hmac.new(
        api_secret.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    signed = dict(params)
    signed["signature"] = signature
    return signed


def should_retry(exc: BinanceRequestError, attempt: int) -> tuple[bool, bool]:
    if attempt >= MAX_RETRY_ATTEMPTS:
        return False, False
    if exc.code == -1021:
        return True, True
    if exc.code in {-2014, -2015}:
        return False, False
    if exc.code == -1003 or exc.status_code in {418, 429}:
        return False, False
    if exc.status_code and 500 <= exc.status_code < 600:
        return True, False
    return False, False


def signed_get(
    client: httpx.Client,
    base_url: str,
    endpoint: str,
    params: dict[str, Any],
    api_key: str,
    api_secret: str,
    offset_ms: int,
) -> Any:
    ensure_endpoint_allowed(endpoint)
    timestamp = int(time.time() * 1000) + offset_ms
    request_params = dict(params)
    request_params["timestamp"] = timestamp
    request_params["recvWindow"] = DEFAULT_RECV_WINDOW
    signed_params = sign_params(request_params, api_secret)
    response = client.get(
        f"{base_url}{endpoint}",
        params=signed_params,
        headers={"X-MBX-APIKEY": api_key},
        timeout=20.0,
    )
    if response.status_code >= 400:
        raise parse_binance_error(response)
    return response.json()


def query_income_type(
    client: httpx.Client,
    ctx: RunContext,
    api_key: str,
    api_secret: str,
    income_type: str,
    sleep_seconds: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page = 1
    while page <= MAX_PAGES_PER_INCOME_TYPE:
        params = {
            "incomeType": income_type,
            "startTime": ctx.start_ms,
            "endTime": ctx.end_ms_request,
            "limit": INCOME_LIMIT,
            "page": page,
        }
        attempt = 1
        while True:
            try:
                payload = signed_get(
                    client,
                    ctx.base_url,
                    ENDPOINT_INCOME,
                    params,
                    api_key,
                    api_secret,
                    ctx.offset_ms or 0,
                )
                ctx.request_count += 1
                break
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= MAX_RETRY_ATTEMPTS:
                    raise BinanceRequestError("network error after retry") from exc
                time.sleep(min(2.0 * attempt, 5.0))
                attempt += 1
            except BinanceRequestError as exc:
                retry, resync = should_retry(exc, attempt)
                if not retry:
                    raise
                if resync:
                    _, ctx.offset_ms = get_server_time(client, ctx.base_url)
                    ctx.request_count += 1
                    if abs(ctx.offset_ms) > OFFSET_BLOCK_MS:
                        raise BlockedError("offset guard blocked after time resync")
                time.sleep(min(2.0 * attempt, 5.0))
                attempt += 1

        if not isinstance(payload, list):
            raise BlockedError("unexpected income response shape")
        rows.extend(payload)
        if len(payload) < INCOME_LIMIT:
            return rows
        page += 1
        time.sleep(sleep_seconds)

    ctx.partial = True
    return rows


def decimal_amount(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal("0")


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_type_asset: dict[str, dict[str, Decimal]] = {
        income_type: defaultdict(Decimal) for income_type in INCOME_TYPES
    }
    by_symbol: dict[tuple[str, str], dict[str, Decimal]] = defaultdict(
        lambda: {income_type: Decimal("0") for income_type in INCOME_TYPES}
    )
    grand_by_asset: dict[str, Decimal] = defaultdict(Decimal)

    for row in rows:
        income_type = str(row.get("incomeType", ""))
        if income_type not in INCOME_TYPES:
            continue
        asset = str(row.get("asset") or "UNKNOWN")
        symbol = str(row.get("symbol") or "NO_SYMBOL")
        amount = decimal_amount(row.get("income"))
        by_type_asset[income_type][asset] += amount
        by_symbol[(symbol, asset)][income_type] += amount
        grand_by_asset[asset] += amount

    return {
        "by_type_asset": by_type_asset,
        "by_symbol": by_symbol,
        "grand_by_asset": grand_by_asset,
    }


def format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def table_for_asset_totals(title: str, values: dict[str, Decimal]) -> list[str]:
    lines = [f"## {title}", "", "| asset | amount |", "|---|---:|"]
    if not values:
        lines.append("| n/a | 0 |")
    else:
        for asset in sorted(values):
            lines.append(f"| {asset} | {format_decimal(values[asset])} |")
    lines.append("")
    return lines


def build_report(ctx: RunContext, rows: list[dict[str, Any]], aggregates: dict[str, Any]) -> str:
    status = "blocked" if ctx.blocked_reason else "partial" if ctx.partial else "ok"
    lines = [
        "# Binance USD-M Futures Income Report",
        "",
        f"- run timestamp: {datetime.now(TAIPEI_TZ).isoformat(timespec='seconds')}",
        f"- mode: {ctx.mode}",
        f"- WILL_SEND_BINANCE_REQUEST: {'YES' if ctx.will_send else 'NO'}",
        f"- base URL label: {ctx.base_url_label}",
        f"- days: {ctx.days}",
        f"- start: {ctx.start_local.isoformat(timespec='seconds')}",
        f"- end: {ctx.end_local.isoformat(timespec='seconds')}",
        f"- request count: {ctx.request_count}",
        f"- status: {status}",
        f"- income endpoint weight: {INCOME_WEIGHT}",
        "- funding fee amount is not funding rate",
        "- different assets are not added together",
    ]
    if ctx.offset_ms is not None:
        lines.append(f"- offset_ms: {ctx.offset_ms}")
    if ctx.live_bot_warning:
        lines.append(f"- warning: {ctx.live_bot_warning}")
    if ctx.blocked_reason:
        lines.append(f"- blocked reason: {ctx.blocked_reason}")
    if ctx.partial:
        lines.append("- partial: pagination limit reached; shorten --days")
    lines.append("")

    by_type_asset = aggregates["by_type_asset"]
    lines.extend(table_for_asset_totals("COMMISSION by asset", by_type_asset["COMMISSION"]))
    lines.extend(table_for_asset_totals("FUNDING_FEE by asset", by_type_asset["FUNDING_FEE"]))

    lines.extend(["## By symbol summary", "", "| symbol | asset | COMMISSION | FUNDING_FEE |", "|---|---|---:|---:|"])
    by_symbol = aggregates["by_symbol"]
    if not by_symbol:
        lines.append("| n/a | n/a | 0 | 0 |")
    else:
        for symbol, asset in sorted(by_symbol):
            values = by_symbol[(symbol, asset)]
            lines.append(
                f"| {symbol} | {asset} | {format_decimal(values['COMMISSION'])} | "
                f"{format_decimal(values['FUNDING_FEE'])} |"
            )
    lines.append("")

    lines.extend(table_for_asset_totals("Grand total by asset", aggregates["grand_by_asset"]))
    lines.append(f"Detail rows fetched: {len(rows)}")
    lines.append("")
    return "\n".join(lines)


def secret_leak_gate(text: str, secrets: list[str]) -> None:
    lowered = text.lower()
    forbidden_markers = [
        "x-mbx-apikey",
        "signature=",
        "api_secret=",
        "api_key=",
        "secret_key=",
        "http headers",
        "signed url",
        "raw query string",
    ]
    for marker in forbidden_markers:
        if marker in lowered:
            raise BlockedError(f"secret leak gate blocked marker: {marker}")
    for secret in secrets:
        if secret and len(secret) >= 8 and secret in text:
            raise BlockedError("secret leak gate blocked raw secret")


def write_report(path: Path, text: str, secrets: list[str]) -> None:
    secret_leak_gate(text, secrets)
    path.write_text(text, encoding="utf-8")


def print_summary(ctx: RunContext) -> None:
    print(f"mode: {ctx.mode}")
    print(f"WILL_SEND_BINANCE_REQUEST: {'YES' if ctx.will_send else 'NO'}")
    print(f"base_url_label: {ctx.base_url_label}")
    print(f"days: {ctx.days}")
    print(f"status: {'blocked' if ctx.blocked_reason else 'partial' if ctx.partial else 'ok'}")
    print(f"request_count: {ctx.request_count}")
    if ctx.blocked_reason:
        print(f"blocked_reason: {ctx.blocked_reason}")
    if ctx.partial:
        print("partial: pagination limit reached; shorten --days")
    if ctx.live_bot_warning:
        print(f"warning: {ctx.live_bot_warning}")
    print(f"report: {ctx.output_report}")


def build_context(args: argparse.Namespace) -> RunContext:
    days = validate_days(args.days)
    base_url, base_url_label = resolve_base_url(args.base_url)
    start_local, end_local, start_ms, end_ms_exclusive, end_ms_request = build_time_range(days)
    output_report = resolve_output_path(args.output_report)
    will_send = bool(args.execute and args.confirm_readonly)
    mode = "execute" if will_send else "dry-run"
    return RunContext(
        mode=mode,
        will_send=will_send,
        base_url=base_url,
        base_url_label=base_url_label,
        days=days,
        start_local=start_local,
        end_local=end_local,
        start_ms=start_ms,
        end_ms_exclusive=end_ms_exclusive,
        end_ms_request=end_ms_request,
        output_report=output_report,
    )


def run() -> int:
    args = parse_args()
    api_key = ""
    api_secret = ""
    rows: list[dict[str, Any]] = []
    aggregates = aggregate_rows(rows)

    try:
        ctx = build_context(args)
        ensure_output_writable(ctx.output_report, args.overwrite)
        ctx.live_bot_warning = detect_live_bot()

        env_values = load_env_values(args.env_file)
        api_key, api_secret = resolve_credentials(
            env_values, args.api_key_var, args.api_secret_var
        )

        if ctx.live_bot_warning and ctx.will_send and args.sleep_seconds < 5.0:
            args.sleep_seconds = 5.0

        if ctx.will_send:
            with httpx.Client(trust_env=True) as client:
                _, ctx.offset_ms = get_server_time(client, ctx.base_url)
                ctx.request_count += 1
                if abs(ctx.offset_ms) > OFFSET_BLOCK_MS:
                    raise BlockedError("offset guard blocked signed income request")
                for income_type in INCOME_TYPES:
                    rows.extend(
                        query_income_type(
                            client,
                            ctx,
                            api_key,
                            api_secret,
                            income_type,
                            args.sleep_seconds,
                        )
                    )
                    time.sleep(args.sleep_seconds)

        aggregates = aggregate_rows(rows)
        report = build_report(ctx, rows, aggregates)
        write_report(ctx.output_report, report, [api_key, api_secret])
        print_summary(ctx)
        return 0

    except BlockedError as exc:
        try:
            ctx
        except UnboundLocalError:
            print(f"BLOCKED: {exc}")
            return 2
        ctx.blocked_reason = str(exc)
        report = build_report(ctx, rows, aggregates)
        try:
            write_report(ctx.output_report, report, [api_key, api_secret])
        except Exception:
            pass
        print_summary(ctx)
        return 2
    except BinanceRequestError as exc:
        ctx.blocked_reason = f"Binance request blocked: status={exc.status_code} code={exc.code}"
        report = build_report(ctx, rows, aggregates)
        try:
            write_report(ctx.output_report, report, [api_key, api_secret])
        except Exception:
            pass
        print_summary(ctx)
        return 2


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
