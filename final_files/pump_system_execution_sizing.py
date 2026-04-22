from __future__ import annotations

from decimal import Decimal

from pump_system.models import SizingDecision, SymbolInfo
from pump_system.utils.decimal_utils import floor_to_step


def build_sizing_decision(
    symbol_info: SymbolInfo,
    price: Decimal,
    available_balance: Decimal,
    target_notional: Decimal,
    max_leverage: int,
) -> SizingDecision:
    """Build a quantity plan that prefers 300 USDT notional and otherwise uses max legal size."""
    if price <= Decimal("0"):
        return SizingDecision(
            symbol=symbol_info.symbol,
            quantity=Decimal("0"),
            requested_notional=target_notional,
            final_notional=Decimal("0"),
            available_balance=available_balance,
            max_affordable_notional=Decimal("0"),
            leverage=max_leverage,
            used_max_affordable=False,
            can_trade=False,
            reason="invalid_price",
        )

    max_affordable_notional = available_balance * Decimal(max_leverage)
    desired_notional = target_notional if max_affordable_notional >= target_notional else max_affordable_notional
    used_max_affordable = desired_notional < target_notional

    lot_min_qty = symbol_info.market_min_qty or symbol_info.min_qty
    lot_max_qty = symbol_info.market_max_qty or symbol_info.max_qty
    lot_step = symbol_info.market_step_size or symbol_info.step_size

    raw_quantity = desired_notional / price if desired_notional > Decimal("0") else Decimal("0")
    quantity = floor_to_step(min(raw_quantity, lot_max_qty), lot_step)
    final_notional = quantity * price

    if quantity < lot_min_qty or final_notional < symbol_info.min_notional:
        max_quantity = floor_to_step(min(max_affordable_notional / price, lot_max_qty), lot_step)
        max_notional = max_quantity * price
        if max_quantity < lot_min_qty or max_notional < symbol_info.min_notional:
            return SizingDecision(
                symbol=symbol_info.symbol,
                quantity=Decimal("0"),
                requested_notional=desired_notional,
                final_notional=max_notional,
                available_balance=available_balance,
                max_affordable_notional=max_affordable_notional,
                leverage=max_leverage,
                used_max_affordable=True,
                can_trade=False,
                reason="below_exchange_minimum",
            )
        quantity = max_quantity
        final_notional = max_notional
        used_max_affordable = True

    return SizingDecision(
        symbol=symbol_info.symbol,
        quantity=quantity,
        requested_notional=desired_notional,
        final_notional=final_notional,
        available_balance=available_balance,
        max_affordable_notional=max_affordable_notional,
        leverage=max_leverage,
        used_max_affordable=used_max_affordable,
        can_trade=quantity > Decimal("0"),
        reason="ok",
    )
