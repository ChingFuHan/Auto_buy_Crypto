import asyncio
from dataclasses import replace
from pathlib import Path

from config import load_settings
from pump_system.fallback_stop.manager import FallbackStopManager


class FakeExchangeClient:
    has_private_api = True


class FakePositionState:
    def __init__(self) -> None:
        self.refreshed = False

    async def refresh(self) -> None:
        self.refreshed = True

    def get_quantity(self, symbol: str):
        return 0


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
