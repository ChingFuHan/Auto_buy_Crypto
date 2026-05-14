import asyncio

from pump_system.state.position_state import PositionState


class FakeExchangeClient:
    has_private_api = True

    def __init__(self) -> None:
        self.position_risk_calls = 0
        self.open_orders_calls = 0
        self.open_algo_orders_calls = 0

    async def get_position_risk(self):
        self.position_risk_calls += 1
        return [
            {
                "symbol": "BTCUSDT",
                "positionAmt": "0.003",
                "entryPrice": "78960",
                "leverage": "21",
                "marginType": "cross",
                "unRealizedProfit": "-0.44",
            }
        ]

    async def get_open_orders(self, symbol: str | None = None):
        self.open_orders_calls += 1
        return [{"symbol": "BTCUSDT"}, {"symbol": "ALTUSDT"}]

    async def get_open_algo_orders(self, symbol=None, algo_type=None):
        self.open_algo_orders_calls += 1
        assert algo_type == "CONDITIONAL"
        if symbol == "BTCUSDT":
            return [{"symbol": "BTCUSDT"}]
        return []


def test_refresh_counts_regular_and_algo_orders() -> None:
    state = PositionState(FakeExchangeClient())

    asyncio.run(state.refresh())

    assert state.has_open_position("BTCUSDT") is True
    assert state.open_order_counts == {"BTCUSDT": 2, "ALTUSDT": 1}
    assert state.get_open_algo_orders("BTCUSDT") == [{"symbol": "BTCUSDT"}]


def test_ensure_fresh_reuses_recent_snapshot() -> None:
    exchange = FakeExchangeClient()
    state = PositionState(exchange)

    async def run_scenario() -> None:
        await state.ensure_fresh(max_age_seconds=10)
        await state.ensure_fresh(max_age_seconds=10)

    asyncio.run(run_scenario())

    assert exchange.position_risk_calls == 1
    assert exchange.open_orders_calls == 1
    assert exchange.open_algo_orders_calls == 2
