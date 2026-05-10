import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from config import load_settings
from pump_system.fallback_stop.manager import FallbackStopManager
from pump_system.models import FallbackStopRecord
from pump_system.utils.client_order_id import is_valid_binance_client_order_id


class FakeExchangeClient:
    has_private_api = True

    def __init__(self) -> None:
        self.orders = []

    async def create_order(self, params):
        self.orders.append(params)
        return {"orderId": 1001}


class FakePositionState:
    def __init__(self, quantity: str = "0") -> None:
        self.refreshed = False
        self.refreshed_symbol = None
        self.quantity = Decimal(quantity)

    async def refresh(self) -> None:
        self.refreshed = True

    async def refresh_symbol(self, symbol: str) -> None:
        self.refreshed_symbol = symbol

    def get_quantity(self, symbol: str):
        return self.quantity


class DummyStagingStore:
    pass


def test_load_existing_drops_stale_active_record(tmp_path: Path) -> None:
    settings = replace(load_settings(), fallback_csv_path=tmp_path / "fallback_stop_state.csv")
    settings.fallback_csv_path.write_text(
        "\n".join(
            [
                "symbol,stop_price,quantity,working_type,active,status,entry_price,entry_order_id,last_price,retry_count,last_error,created_at,updated_at",
                "BTCUSDT,78901.60,0.003,CONTRACT_PRICE,True,ACTIVE,78960.00000,992981044417,78959.90,3,native_stop_failed,2026-04-22T19:25:29.557458+00:00,2026-04-22T19:25:29.557458+00:00",
            ]
        ),
        encoding="utf-8",
    )
    position_state = FakePositionState()
    manager = FallbackStopManager(
        settings=settings,
        exchange_client=FakeExchangeClient(),
        position_state=position_state,
        staging_store=DummyStagingStore(),
        notifier=None,
    )

    asyncio.run(manager.load_existing())

    assert position_state.refreshed is True
    assert manager.records == {}
    rows = asyncio.run(manager.csv_state.load_rows())
    assert rows[0]["active"] == "False"
    assert rows[0]["status"] == "POSITION_ALREADY_CLOSED"


def test_fallback_close_client_order_id_sanitizes_non_ascii_symbol(tmp_path: Path) -> None:
    settings = replace(
        load_settings(),
        enable_live_trading=True,
        fallback_csv_path=tmp_path / "fallback_stop_state.csv",
    )
    exchange_client = FakeExchangeClient()
    position_state = FakePositionState(quantity="189")
    manager = FallbackStopManager(
        settings=settings,
        exchange_client=exchange_client,
        position_state=position_state,
        staging_store=DummyStagingStore(),
        notifier=None,
    )
    now = datetime.now(timezone.utc)
    record = FallbackStopRecord(
        symbol="币安人生USDT",
        stop_price=Decimal("0.38819"),
        quantity=Decimal("189"),
        working_type="CONTRACT_PRICE",
        active=True,
        status="ACTIVE",
        entry_price=Decimal("0.39550"),
        entry_order_id="1000",
        last_price=None,
        retry_count=0,
        last_error="native_stop_failed",
        created_at=now,
        updated_at=now,
    )
    manager.records[record.symbol] = record

    asyncio.run(manager._trigger_close(record, Decimal("0.38800")))

    assert position_state.refreshed_symbol == "币安人生USDT"
    assert exchange_client.orders[0]["symbol"] == "币安人生USDT"
    client_order_id = exchange_client.orders[0]["newClientOrderId"]
    assert client_order_id.startswith("fallback_usdt_")
    assert "币" not in client_order_id
    assert len(client_order_id) <= 36
    assert is_valid_binance_client_order_id(client_order_id)
