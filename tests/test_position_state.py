import asyncio

from pump_system.state.position_state import PositionState


class FakeExchangeClient:
    has_private_api = True

    async def get_position_risk(self):
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

    async def get_open_orders(self):
        return [{"symbol": "BTCUSDT"}, {"symbol": "ALTUSDT"}]

    async def get_open_algo_orders(self, symbol=None, algo_type=None):
        assert algo_type == "CONDITIONAL"
        if symbol == "BTCUSDT":
            return [{"symbol": "BTCUSDT"}]
        return []


def test_refresh_counts_regular_and_algo_orders() -> None:
    state = PositionState(FakeExchangeClient())

    asyncio.run(state.refresh())

    assert state.has_open_position("BTCUSDT") is True
    assert state.open_order_counts == {"BTCUSDT": 2, "ALTUSDT": 1}
