import asyncio
from decimal import Decimal

from config import load_settings
from pump_system.execution.order_service import OrderService
from pump_system.models import NativeStopTracker, SignalDecision


class DummyExchangeClient:
    def __init__(self) -> None:
        self.params = None
        self.orders = []
        self.has_private_api = True

    async def create_algo_order(self, params):
        self.params = params
        return {"algoId": 123456}

    async def get_position_risk(self, symbol=None):
        return [{"symbol": "BTCUSDT", "positionSide": "LONG", "positionAmt": "0"}]

    async def get_open_algo_orders(self, symbol=None, algo_type=None):
        return []

    async def get_all_orders(self, symbol, limit=20):
        return list(self.orders)


class DummyPositionState:
    pass


class DummySymbolRegistry:
    pass


class DummyStagingStore:
    pass


class DummySignalEngine:
    pass


class DummyFallbackManager:
    pass


class DummyNotifier:
    def __init__(self) -> None:
        self.trade_events = []
        self.error_events = []
        self.warning_events = []

    async def send_trade(self, event_type, **kwargs):
        self.trade_events.append((event_type, kwargs))

    async def send_error(self, event_type, **kwargs):
        self.error_events.append((event_type, kwargs))

    async def send_warning(self, event_type, **kwargs):
        self.warning_events.append((event_type, kwargs))


def test_native_stop_uses_algo_order_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("STOP_WORKING_TYPE", "MARK_PRICE")
    settings = load_settings()
    exchange_client = DummyExchangeClient()
    notifier = DummyNotifier()
    service = OrderService(
        settings=settings,
        exchange_client=exchange_client,
        symbol_registry=DummySymbolRegistry(),
        staging_store=DummyStagingStore(),
        position_state=DummyPositionState(),
        signal_engine=DummySignalEngine(),
        fallback_manager=DummyFallbackManager(),
        notifier=notifier,
    )
    decision = SignalDecision(
        symbol="BTCUSDT",
        triggered=True,
        reason="test",
        stop_reference_low=Decimal("78821.0"),
        current_price=Decimal("78830.0"),
    )

    result = asyncio.run(
        service._place_exchange_stop(
            "BTCUSDT",
            decision,
            {"executedQty": "0.003", "avgPrice": "78830.0"},
        )
    )

    assert result is True
    assert exchange_client.params is not None
    assert exchange_client.params["algoType"] == "CONDITIONAL"
    assert exchange_client.params["symbol"] == "BTCUSDT"
    assert exchange_client.params["side"] == "SELL"
    assert exchange_client.params["positionSide"] == "LONG"
    assert exchange_client.params["type"] == "STOP_MARKET"
    assert exchange_client.params["triggerPrice"] == "78821"
    assert exchange_client.params["workingType"] == "MARK_PRICE"
    assert exchange_client.params["closePosition"] == "true"
    assert exchange_client.params["clientAlgoId"].startswith("stop_btcusdt_")
    assert notifier.trade_events[0][0] == "STOP_ORDER_SUCCESS"


def test_reconcile_native_stop_reports_trigger_to_telegram() -> None:
    settings = load_settings()
    exchange_client = DummyExchangeClient()
    notifier = DummyNotifier()
    exchange_client.orders = [
        {
            "clientOrderId": "stop_btcusdt_123",
            "status": "FILLED",
            "orderId": 999001,
            "executedQty": "0.003",
            "avgPrice": "78764.9",
        }
    ]
    service = OrderService(
        settings=settings,
        exchange_client=exchange_client,
        symbol_registry=DummySymbolRegistry(),
        staging_store=DummyStagingStore(),
        position_state=DummyPositionState(),
        signal_engine=DummySignalEngine(),
        fallback_manager=DummyFallbackManager(),
        notifier=notifier,
    )
    service._active_native_stops["BTCUSDT"] = NativeStopTracker(
        symbol="BTCUSDT",
        client_order_id="stop_btcusdt_123",
        algo_id="40001",
        stop_price=Decimal("78765.9"),
        quantity=Decimal("0.003"),
        working_type="CONTRACT_PRICE",
        entry_price=Decimal("78770.0"),
    )

    asyncio.run(service.reconcile_native_stops())

    assert "BTCUSDT" not in service._active_native_stops
    assert notifier.trade_events[0][0] == "STOP_ORDER_TRIGGERED"
    assert notifier.trade_events[0][1]["order_id"] == 999001
