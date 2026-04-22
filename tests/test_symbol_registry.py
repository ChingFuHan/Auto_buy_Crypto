from config import load_settings
from pump_system.exchange.symbol_registry import SymbolRegistry


def test_function_test_symbol_is_evaluated_even_if_excluded(monkeypatch) -> None:
    monkeypatch.setenv("FUNCTION_TEST_MODE", "true")
    monkeypatch.setenv("FUNCTION_TEST_SYMBOL", "BTCUSDT")
    monkeypatch.delenv("SYMBOL_WHITELIST", raising=False)
    monkeypatch.delenv("SYMBOL_BLACKLIST", raising=False)
    settings = load_settings()
    registry = SymbolRegistry(settings)

    exchange_info = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "status": "TRADING",
                "contractType": "PERPETUAL",
                "quoteAsset": "USDT",
                "marginAsset": "USDT",
                "triggerProtect": "0.15",
                "orderTypes": ["MARKET", "STOP_MARKET"],
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.1"},
                    {"filterType": "LOT_SIZE", "minQty": "0.001", "maxQty": "1000", "stepSize": "0.001"},
                    {"filterType": "MARKET_LOT_SIZE", "minQty": "0.001", "maxQty": "1000", "stepSize": "0.001"},
                    {"filterType": "MIN_NOTIONAL", "notional": "5"},
                ],
            },
            {
                "symbol": "ALTUSDT",
                "status": "TRADING",
                "contractType": "PERPETUAL",
                "quoteAsset": "USDT",
                "marginAsset": "USDT",
                "triggerProtect": "0.15",
                "orderTypes": ["MARKET", "STOP_MARKET"],
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.0001"},
                    {"filterType": "LOT_SIZE", "minQty": "1", "maxQty": "100000", "stepSize": "1"},
                    {"filterType": "MARKET_LOT_SIZE", "minQty": "1", "maxQty": "100000", "stepSize": "1"},
                    {"filterType": "MIN_NOTIONAL", "notional": "5"},
                ],
            },
        ]
    }

    registry.refresh_from_exchange_info(exchange_info)

    assert registry.is_candidate("BTCUSDT") is False
    assert registry.should_evaluate("BTCUSDT") is True
    assert registry.should_evaluate("ALTUSDT") is True
    assert registry.evaluation_symbols() == {"BTCUSDT", "ALTUSDT"}
