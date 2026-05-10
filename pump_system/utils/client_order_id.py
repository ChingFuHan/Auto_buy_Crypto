from __future__ import annotations

import hashlib
import re


BINANCE_CLIENT_ORDER_ID_MAX_LENGTH = 36
_BINANCE_CLIENT_ORDER_ID_RE = re.compile(r"^[.A-Z:/a-z0-9_-]{1,36}$")
_UNSAFE_COMPONENT_CHARS_RE = re.compile(r"[^a-z0-9_-]+")


def is_valid_binance_client_order_id(value: str) -> bool:
    return bool(_BINANCE_CLIENT_ORDER_ID_RE.fullmatch(value))


def build_binance_client_order_id(
    prefix: str,
    symbol: str,
    *suffix_parts: object,
    max_length: int = BINANCE_CLIENT_ORDER_ID_MAX_LENGTH,
) -> str:
    """Build a Binance-safe client id without altering the exchange symbol."""
    prefix_part = _safe_component(prefix, fallback="id")
    suffixes = [_safe_component(str(part), fallback="x") for part in suffix_parts]
    separator_count = 1 + len(suffixes)
    reserved_length = len(prefix_part) + sum(len(part) for part in suffixes) + separator_count
    max_symbol_length = max(max_length - reserved_length, 1)
    symbol_part = _safe_symbol_component(symbol, max_symbol_length)

    parts = [prefix_part, symbol_part, *suffixes]
    value = "_".join(parts)
    if len(value) > max_length:
        overflow = len(value) - max_length
        symbol_part = symbol_part[:-overflow] if overflow < len(symbol_part) else symbol_part[:1]
        value = "_".join([prefix_part, symbol_part, *suffixes])

    if not is_valid_binance_client_order_id(value):
        raise ValueError(f"invalid Binance client order id generated: {value!r}")
    return value


def _safe_component(value: str, *, fallback: str) -> str:
    component = _UNSAFE_COMPONENT_CHARS_RE.sub("", value.strip().lower())
    return component or fallback


def _safe_symbol_component(symbol: str, max_length: int) -> str:
    normalized = symbol.strip().lower()
    cleaned = _UNSAFE_COMPONENT_CHARS_RE.sub("", normalized)
    if cleaned and cleaned == normalized:
        return cleaned[:max_length]

    digest = hashlib.blake2s(symbol.encode("utf-8"), digest_size=4).hexdigest()
    if max_length <= len(digest) + 1:
        return f"s{digest}"[:max_length]
    if cleaned:
        head_length = max_length - len(digest) - 1
        head = cleaned[:head_length] or "s"
        return f"{head}_{digest}"
    return f"s{digest}"[:max_length]
