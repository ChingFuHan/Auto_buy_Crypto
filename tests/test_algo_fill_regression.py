"""Regression tests for algo order fill detection in reconcile_native_stops
and restore_native_stop_watchlist.

These tests cover the exact Binance API response field names consumed by the native
stop monitor, so that future Binance API changes can be caught early.

Known Gap (documented explicitly below):
    When Binance assigns a system-generated clientOrderId to the triggered child
    order that does NOT match the original clientAlgoId, _find_order_by_client_id()
    returns None and reconcile degrades to STOP_ORDER_POSITION_CLOSED (a warning,
    not a confirmed fill). This is acceptable today but would be improved by an
    algo-history fallback using actualOrderId / actualQty / actualPrice fields.
    See HANDOFF.md [RISK] note and the xfail test at the bottom of this file.
"""

import asyncio
from decimal import Decimal

import pytest

from config import load_settings
from pump_system.execution.order_service import OrderService
from pump_system.models import NativeStopTracker, PositionSnapshot
from pump_system.state.position_state import PositionState


# ──────────────────────────────────────────────────────────────────────────────
# Test doubles
# ──────────────────────────────────────────────────────────────────────────────


class _FakeExchange:
    """Configurable test double — configure return values via public attributes."""

    has_private_api = True

    def __init__(self) -> None:
        self.position_risk: list[dict] = []
        self.open_algo_orders: list[dict] = []
        self.all_orders: list[dict] = []
        # Future: populated when get_historical_algo_orders() is implemented
        self.historical_algo_orders: list[dict] = []

    async def get_position_risk(self, symbol: str | None = None) -> list[dict]:
        if symbol:
            return [p for p in self.position_risk if p.get("symbol") == symbol]
        return list(self.position_risk)

    async def get_open_algo_orders(self, symbol: str | None = None, algo_type: str | None = None) -> list[dict]:
        result = list(self.open_algo_orders)
        if symbol:
            result = [o for o in result if o.get("symbol") == symbol]
        return result

    async def get_all_orders(self, symbol: str, limit: int = 20) -> list[dict]:
        result = [o for o in self.all_orders if o.get("symbol") == symbol]
        return result[-limit:] if len(result) > limit else result

    async def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        return []

    # Placeholder for the future fallback method (not yet implemented in BinanceClient)
    async def get_historical_algo_orders(
        self, symbol: str | None = None, algo_type: str | None = None, limit: int = 50
    ) -> list[dict]:
        result = list(self.historical_algo_orders)
        if symbol:
            result = [o for o in result if o.get("symbol") == symbol]
        return result


class _DummyNotifier:
    def __init__(self) -> None:
        self.trade_events: list[tuple[str, dict]] = []
        self.error_events: list[tuple[str, dict]] = []
        self.warning_events: list[tuple[str, dict]] = []

    async def send_trade(self, event_type: str, **kwargs: object) -> None:
        self.trade_events.append((event_type, kwargs))

    async def send_error(self, event_type: str, **kwargs: object) -> None:
        self.error_events.append((event_type, kwargs))

    async def send_warning(self, event_type: str, **kwargs: object) -> None:
        self.warning_events.append((event_type, kwargs))


class _DummyStub:
    pass


def _make_service(exchange: _FakeExchange, notifier: _DummyNotifier) -> OrderService:
    settings = load_settings()
    position_state = PositionState(exchange, enable_open_order_sync=False)
    return OrderService(
        settings=settings,
        exchange_client=exchange,
        symbol_registry=_DummyStub(),
        staging_store=_DummyStub(),
        position_state=position_state,
        signal_engine=_DummyStub(),
        fallback_manager=_DummyStub(),
        notifier=notifier,
    )


def _seed_position(
    service: OrderService,
    symbol: str,
    qty: str = "0.003",
    entry_price: str = "78000.0",
) -> None:
    service.position_state.positions[symbol] = PositionSnapshot(
        symbol=symbol,
        quantity=Decimal(qty),
        entry_price=Decimal(entry_price),
        leverage=10,
        margin_type="cross",
        unrealized_pnl=Decimal("0"),
    )


def _seed_tracker(
    service: OrderService,
    symbol: str,
    client_order_id: str = "stop_btcusdt_111",
    algo_id: str = "9001",
    stop_price: str = "78000.0",
    qty: str = "0.003",
    entry_price: str = "78100.0",
) -> None:
    service._active_native_stops[symbol] = NativeStopTracker(
        symbol=symbol,
        client_order_id=client_order_id,
        algo_id=algo_id,
        stop_price=Decimal(stop_price),
        quantity=Decimal(qty),
        working_type="MARK_PRICE",
        entry_price=Decimal(entry_price),
    )


# ──────────────────────────────────────────────────────────────────────────────
# restore_native_stop_watchlist field-name regression
# ──────────────────────────────────────────────────────────────────────────────


def test_restore_watchlist_extracts_all_algo_response_fields() -> None:
    """All field names read from open-algo-orders response are explicitly asserted.

    If Binance renames any of these keys, this test will fail immediately.
    Fields: clientAlgoId, algoId, orderType, positionSide, triggerPrice, workingType.
    """
    exchange = _FakeExchange()
    notifier = _DummyNotifier()
    service = _make_service(exchange, notifier)

    _seed_position(service, "BTCUSDT", qty="0.003", entry_price="78960.0")

    exchange.open_algo_orders = [
        {
            "symbol": "BTCUSDT",
            "clientAlgoId": "stop_btcusdt_99999",  # → tracker.client_order_id
            "algoId": "40001234",                   # → tracker.algo_id
            "orderType": "STOP_MARKET",             # gate: must be STOP_MARKET
            "positionSide": "LONG",                 # gate: must be LONG
            "triggerPrice": "78000.5",              # → tracker.stop_price
            "workingType": "MARK_PRICE",            # → tracker.working_type
            "side": "SELL",
        }
    ]

    asyncio.run(service.restore_native_stop_watchlist())

    assert "BTCUSDT" in service._active_native_stops
    tracker = service._active_native_stops["BTCUSDT"]
    assert tracker.client_order_id == "stop_btcusdt_99999"
    assert tracker.algo_id == "40001234"
    assert tracker.stop_price == Decimal("78000.5")
    assert tracker.working_type == "MARK_PRICE"


def test_restore_watchlist_skips_orders_with_wrong_type_side_or_prefix() -> None:
    """restore_native_stop_watchlist must filter by orderType, positionSide, and clientAlgoId prefix.

    Only the order with orderType=STOP_MARKET, positionSide=LONG, and clientAlgoId
    starting with 'stop_' must be restored. The other three distractor orders must
    not produce a tracker entry, even though they share the same symbol.
    """
    exchange = _FakeExchange()
    service = _make_service(exchange, _DummyNotifier())

    _seed_position(service, "BTCUSDT", qty="0.003")

    exchange.open_algo_orders = [
        # wrong orderType — must be skipped
        {
            "symbol": "BTCUSDT", "clientAlgoId": "stop_btcusdt_1", "algoId": "1",
            "orderType": "TAKE_PROFIT", "positionSide": "LONG",
            "triggerPrice": "80000", "workingType": "MARK_PRICE",
        },
        # wrong positionSide — must be skipped
        {
            "symbol": "BTCUSDT", "clientAlgoId": "stop_btcusdt_2", "algoId": "2",
            "orderType": "STOP_MARKET", "positionSide": "SHORT",
            "triggerPrice": "80000", "workingType": "MARK_PRICE",
        },
        # wrong clientAlgoId prefix (Android-originated stop) — must be skipped
        {
            "symbol": "BTCUSDT", "clientAlgoId": "android_btcusdt_3", "algoId": "3",
            "orderType": "STOP_MARKET", "positionSide": "LONG",
            "triggerPrice": "80000", "workingType": "MARK_PRICE",
        },
        # valid — must be the only one restored
        {
            "symbol": "BTCUSDT", "clientAlgoId": "stop_btcusdt_4", "algoId": "4",
            "orderType": "STOP_MARKET", "positionSide": "LONG",
            "triggerPrice": "77999.0", "workingType": "CONTRACT_PRICE",
        },
    ]

    asyncio.run(service.restore_native_stop_watchlist())

    assert "BTCUSDT" in service._active_native_stops
    # Specifically the valid order (algoId "4"), not any distractor
    assert service._active_native_stops["BTCUSDT"].algo_id == "4"


# ──────────────────────────────────────────────────────────────────────────────
# reconcile_native_stops field-name regression
# ──────────────────────────────────────────────────────────────────────────────


def test_reconcile_fill_extracts_order_id_executedqty_avgprice() -> None:
    """All fields consumed from the allOrders response during fill detection are asserted.

    Fields: clientOrderId (matching key), orderId, executedQty, avgPrice, status.
    A distractor order with a different clientOrderId must not interfere.
    """
    exchange = _FakeExchange()
    notifier = _DummyNotifier()
    service = _make_service(exchange, notifier)

    _seed_tracker(service, "BTCUSDT", client_order_id="stop_btcusdt_111",
                  algo_id="9001", stop_price="78000.0", qty="0.003", entry_price="78100.0")

    exchange.position_risk = [
        {"symbol": "BTCUSDT", "positionSide": "LONG", "positionAmt": "0"}
    ]
    exchange.open_algo_orders = []
    exchange.all_orders = [
        # distractor — different clientOrderId, must not match
        {
            "symbol": "BTCUSDT", "clientOrderId": "entry_btcusdt_000",
            "status": "FILLED", "orderId": 111, "executedQty": "0.999", "avgPrice": "99999.9",
        },
        # the real fill — must be matched by clientOrderId
        {
            "symbol": "BTCUSDT", "clientOrderId": "stop_btcusdt_111",
            "status": "FILLED", "orderId": 88881, "executedQty": "0.003", "avgPrice": "77995.0",
        },
    ]

    asyncio.run(service.reconcile_native_stops())

    assert "BTCUSDT" not in service._active_native_stops
    assert len(notifier.trade_events) == 1
    event_type, kwargs = notifier.trade_events[0]
    assert event_type == "STOP_ORDER_TRIGGERED"
    assert kwargs["order_id"] == 88881
    assert kwargs["details"]["fill_price"] == "77995.0"
    # executedQty from response must be used, not tracker fallback
    assert kwargs["quantity"] == "0.003"


def test_reconcile_fill_falls_back_to_tracker_qty_when_executedqty_absent() -> None:
    """When executedQty is absent from allOrders response, quantity falls back to tracker.quantity."""
    exchange = _FakeExchange()
    notifier = _DummyNotifier()
    service = _make_service(exchange, notifier)

    _seed_tracker(service, "BTCUSDT", client_order_id="stop_btcusdt_222", qty="0.005")

    exchange.position_risk = [
        {"symbol": "BTCUSDT", "positionSide": "LONG", "positionAmt": "0"}
    ]
    exchange.open_algo_orders = []
    exchange.all_orders = [
        # executedQty intentionally absent — should fall back to tracker.quantity
        {
            "symbol": "BTCUSDT", "clientOrderId": "stop_btcusdt_222",
            "status": "FILLED", "orderId": 99001, "avgPrice": "78050.0",
        },
    ]

    asyncio.run(service.reconcile_native_stops())

    assert len(notifier.trade_events) == 1
    _, kwargs = notifier.trade_events[0]
    assert notifier.trade_events[0][0] == "STOP_ORDER_TRIGGERED"
    # Must fall back to tracker.quantity (Decimal) when executedQty is missing
    assert kwargs["quantity"] == Decimal("0.005")


def test_reconcile_continues_when_position_open_and_algo_present() -> None:
    """No notification and tracker untouched when position is open AND matching algo still visible.

    This guards the race condition where the monitor fires between position closure
    and algo disappearance — both must be gone before any state change.
    """
    exchange = _FakeExchange()
    notifier = _DummyNotifier()
    service = _make_service(exchange, notifier)

    _seed_tracker(service, "BTCUSDT", client_order_id="stop_btcusdt_333", algo_id="5555")

    # position still open
    exchange.position_risk = [
        {"symbol": "BTCUSDT", "positionSide": "LONG", "positionAmt": "0.003"}
    ]
    # algo still present
    exchange.open_algo_orders = [
        {"symbol": "BTCUSDT", "clientAlgoId": "stop_btcusdt_333", "algoId": "5555"}
    ]

    asyncio.run(service.reconcile_native_stops())

    assert "BTCUSDT" in service._active_native_stops
    assert notifier.trade_events == []
    assert notifier.error_events == []
    assert notifier.warning_events == []


def test_reconcile_stop_missing_emits_error_and_deduplicates() -> None:
    """STOP_ORDER_MISSING is emitted once when position is open but algo vanished.

    Calling reconcile a second time must NOT emit a duplicate notification
    (guarded by tracker.missing_reported).
    """
    exchange = _FakeExchange()
    notifier = _DummyNotifier()
    service = _make_service(exchange, notifier)

    _seed_tracker(service, "BTCUSDT", client_order_id="stop_btcusdt_444", algo_id="7777")

    # position still open
    exchange.position_risk = [
        {"symbol": "BTCUSDT", "positionSide": "LONG", "positionAmt": "0.003"}
    ]
    # algo gone
    exchange.open_algo_orders = []

    asyncio.run(service.reconcile_native_stops())
    asyncio.run(service.reconcile_native_stops())

    # tracker must remain (not removed — position is still open)
    assert "BTCUSDT" in service._active_native_stops
    assert service._active_native_stops["BTCUSDT"].missing_reported is True

    # error emitted exactly once despite two reconcile calls
    missing_errors = [e for e in notifier.error_events if e[0] == "STOP_ORDER_MISSING"]
    assert len(missing_errors) == 1


# ──────────────────────────────────────────────────────────────────────────────
# Known-gap characterisation test
# ──────────────────────────────────────────────────────────────────────────────


def test_reconcile_position_closed_when_clientorderid_mismatch__known_gap() -> None:
    """CHARACTERISATION TEST — documents known degradation path, not the desired behaviour.

    Current behaviour: if Binance assigns a system-generated clientOrderId to the
    child order (not matching clientAlgoId), _find_order_by_client_id returns None
    and reconcile degrades to STOP_ORDER_POSITION_CLOSED (warning only, no crash).

    This is an acceptable degradation today (the position IS closed; we only fail
    to confirm it was the native stop that closed it). The planned mitigation is an
    algo-history fallback using actualOrderId / actualQty / actualPrice.
    See HANDOFF.md [RISK] note and test_reconcile_triggered_via_algo_history_fallback.
    """
    exchange = _FakeExchange()
    notifier = _DummyNotifier()
    service = _make_service(exchange, notifier)

    _seed_tracker(service, "BTCUSDT", client_order_id="stop_btcusdt_555", algo_id="8888")

    exchange.position_risk = [
        {"symbol": "BTCUSDT", "positionSide": "LONG", "positionAmt": "0"}
    ]
    exchange.open_algo_orders = []
    # allOrders: FILLED child order with a Binance-generated id that does NOT match
    exchange.all_orders = [
        {
            "symbol": "BTCUSDT", "clientOrderId": "binance_generated_id_xyz",
            "status": "FILLED", "orderId": 55501, "executedQty": "0.003", "avgPrice": "77900.0",
        }
    ]

    asyncio.run(service.reconcile_native_stops())

    # Tracker removed (position is closed)
    assert "BTCUSDT" not in service._active_native_stops
    # Current degraded behaviour: warning POSITION_CLOSED, NOT the preferred TRIGGERED
    assert len(notifier.warning_events) == 1
    assert notifier.warning_events[0][0] == "STOP_ORDER_POSITION_CLOSED"
    assert notifier.trade_events == []


# ──────────────────────────────────────────────────────────────────────────────
# Future-behaviour xfail — algo history fallback (HANDOFF.md [RISK] mitigation)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Algo-history fallback not yet implemented. "
        "Implement get_historical_algo_orders() in BinanceClient (GET /fapi/v1/algoOrders) "
        "and update reconcile_native_stops() to fall back to it when _find_order_by_client_id "
        "returns None — matching by algoId and reading actualOrderId / actualQty / actualPrice. "
        "When implemented, remove the xfail decorator. See HANDOFF.md [RISK]."
    ),
)
def test_reconcile_triggered_via_algo_history_fallback() -> None:
    """DESIRED FUTURE BEHAVIOUR — must become a passing test once the fallback is implemented.

    When clientOrderId of the child order does not match clientAlgoId, reconcile
    should fall back to querying GET /fapi/v1/algoOrders by symbol, match on algoId,
    and emit STOP_ORDER_TRIGGERED using actualOrderId / actualQty / actualPrice from
    the algo history response.
    """
    exchange = _FakeExchange()
    notifier = _DummyNotifier()
    service = _make_service(exchange, notifier)

    _seed_tracker(service, "BTCUSDT", client_order_id="stop_btcusdt_666", algo_id="9999")

    exchange.position_risk = [
        {"symbol": "BTCUSDT", "positionSide": "LONG", "positionAmt": "0"}
    ]
    exchange.open_algo_orders = []
    # allOrders: no clientOrderId match
    exchange.all_orders = []
    # Algo history: COMPLETED entry with actual execution details
    exchange.historical_algo_orders = [
        {
            "symbol": "BTCUSDT",
            "algoId": "9999",
            "algoStatus": "COMPLETED",     # or "FILLED" — to be confirmed with Binance docs
            "clientAlgoId": "stop_btcusdt_666",
            "actualOrderId": 66601,        # the real child order id
            "actualQty": "0.003",          # actual filled quantity
            "actualPrice": "77950.0",      # actual average fill price
        }
    ]

    asyncio.run(service.reconcile_native_stops())

    assert "BTCUSDT" not in service._active_native_stops
    assert len(notifier.trade_events) == 1
    event_type, kwargs = notifier.trade_events[0]
    assert event_type == "STOP_ORDER_TRIGGERED"
    assert kwargs["order_id"] == 66601
    assert kwargs["details"]["fill_price"] == "77950.0"
