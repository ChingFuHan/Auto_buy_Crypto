from decimal import Decimal

from pump_system.execution.sizing import build_sizing_decision
from pump_system.models import SymbolInfo


def build_symbol() -> SymbolInfo:
    return SymbolInfo(
        symbol="TESTUSDT",
        status="TRADING",
        contract_type="PERPETUAL",
        quote_asset="USDT",
        margin_asset="USDT",
        tick_size=Decimal("0.0001"),
        min_qty=Decimal("1"),
        max_qty=Decimal("100000"),
        step_size=Decimal("1"),
        market_min_qty=Decimal("1"),
        market_max_qty=Decimal("100000"),
        market_step_size=Decimal("1"),
        min_notional=Decimal("5"),
        trigger_protect=Decimal("0.15"),
        order_types=("MARKET", "STOP_MARKET"),
    )


def test_uses_target_notional_when_balance_is_enough() -> None:
    decision = build_sizing_decision(
        symbol_info=build_symbol(),
        price=Decimal("2"),
        available_balance=Decimal("20"),
        target_notional=Decimal("30"),
        max_leverage=5,
    )
    assert decision.can_trade is True
    assert decision.quantity == Decimal("15")
    assert decision.used_max_affordable is False


def test_uses_max_affordable_when_balance_is_small() -> None:
    decision = build_sizing_decision(
        symbol_info=build_symbol(),
        price=Decimal("10"),
        available_balance=Decimal("2"),
        target_notional=Decimal("300"),
        max_leverage=5,
    )
    assert decision.can_trade is True
    assert decision.quantity == Decimal("1")
    assert decision.used_max_affordable is True


def test_rejects_when_even_minimum_is_unreachable() -> None:
    decision = build_sizing_decision(
        symbol_info=build_symbol(),
        price=Decimal("100"),
        available_balance=Decimal("0.01"),
        target_notional=Decimal("300"),
        max_leverage=2,
    )
    assert decision.can_trade is False
    assert decision.reason == "below_exchange_minimum"
