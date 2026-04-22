from __future__ import annotations

from dataclasses import dataclass

from config import Settings
from pump_system.models import SymbolInfo


@dataclass(slots=True)
class SymbolRefreshResult:
    previous_data_symbols: set[str]
    current_data_symbols: set[str]
    previous_candidate_symbols: set[str]
    current_candidate_symbols: set[str]

    @property
    def data_symbols_changed(self) -> bool:
        return self.previous_data_symbols != self.current_data_symbols

    @property
    def candidate_symbols_changed(self) -> bool:
        return self.previous_candidate_symbols != self.current_candidate_symbols


class SymbolRegistry:
    """Keeps the all-USDT-perpetual universe and the strategy candidate universe."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.symbols: dict[str, SymbolInfo] = {}
        self.data_symbols: set[str] = set()
        self.candidate_symbols: set[str] = set()

    def refresh_from_exchange_info(self, exchange_info: dict) -> SymbolRefreshResult:
        previous_data_symbols = set(self.data_symbols)
        previous_candidate_symbols = set(self.candidate_symbols)

        symbols: dict[str, SymbolInfo] = {}
        data_symbols: set[str] = set()
        for payload in exchange_info.get("symbols", []):
            if payload.get("quoteAsset") != "USDT":
                continue
            if payload.get("contractType") != "PERPETUAL":
                continue
            if payload.get("status") != "TRADING":
                continue

            info = SymbolInfo.from_exchange_payload(payload)
            symbols[info.symbol] = info
            data_symbols.add(info.symbol)

        if self.settings.symbol_whitelist:
            candidate_symbols = set(self.settings.symbol_whitelist).intersection(data_symbols)
        else:
            candidate_symbols = set(data_symbols)
            candidate_symbols.difference_update(self.settings.excluded_big_caps)
            candidate_symbols.difference_update(self.settings.symbol_blacklist)

        self.symbols = symbols
        self.data_symbols = data_symbols
        self.candidate_symbols = candidate_symbols

        return SymbolRefreshResult(
            previous_data_symbols=previous_data_symbols,
            current_data_symbols=set(self.data_symbols),
            previous_candidate_symbols=previous_candidate_symbols,
            current_candidate_symbols=set(self.candidate_symbols),
        )

    def is_candidate(self, symbol: str) -> bool:
        return symbol in self.candidate_symbols

    def is_function_test_symbol(self, symbol: str) -> bool:
        return (
            self.settings.function_test_mode
            and symbol == self.settings.function_test_symbol
            and symbol in self.data_symbols
        )

    def should_evaluate(self, symbol: str) -> bool:
        return self.is_candidate(symbol) or self.is_function_test_symbol(symbol)

    def evaluation_symbols(self) -> set[str]:
        symbols = set(self.candidate_symbols)
        if self.is_function_test_symbol(self.settings.function_test_symbol):
            symbols.add(self.settings.function_test_symbol)
        return symbols

    def get(self, symbol: str) -> SymbolInfo | None:
        return self.symbols.get(symbol)
