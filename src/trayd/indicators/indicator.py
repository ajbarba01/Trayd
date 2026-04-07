import numpy as np

from trayd.util import Logger

from trayd.util.helpers import mean


class Indicator:
    def __init__(self, name: str):
        self.name = name
        self.warmup_window = 0
        self.key = -1

        self.signature = self._get_signature()
        self.dependencies: list[Indicator] = []

        self.historical = None
        self.indicator_data = None


    def get_warmup_window(self) -> int:
        return 0


    def _get_settings(self) -> list[int]:
        return []
    

    def get_prereqs(self) -> list:
        return []
    

    def _get_signature(self) -> str:
        settings = [str(x) for x in self._get_settings()]
        return f"{self.name}({','.join(settings)})"


    def compute(self):
        pass


    def get(self, symbol: str, offset: int = 0) -> float:
        value = self.historical.get_indicator_data(symbol, self.key, offset)
        # value = self.indicator_data[
        #     self.historical.symbol_index[symbol],
        #     self.key,
        #     self.historical.current_ts_idx + offset
        # ]
        # if np.isnan(value): Logger.log_error(f"NAN indicator {self.signature}: {symbol}, {self.historical.current_ts}")
        return value
    

    def __call__(self, symbol: str, offset: int = 0):
        return self.get(symbol, offset)
    

    def rank(self, symbols: list[str], offset: int = 0, descending: bool = True, max_len = None) -> list[str]:
        # Build a dictionary of symbol -> indicator value
        values = {}
        for s in symbols:
            values[s] = self.get(s, offset)


        sorted_symbols = sorted(values.keys(), key=lambda x: values[x], reverse=descending)
        if max_len:
            return sorted_symbols[:min(len(sorted_symbols), max_len)]
        
        return sorted_symbols
    

    def compare(self, symbols: list[str], target_value: float, offset: int = 0) -> list[str]:
        return [symbol for symbol in symbols if self.get(symbol, offset=offset) == target_value]
    

    def filter(self, symbols: list[str], offset: int = 0, lower_val: float = -float('inf'), upper_val: float = float('inf')) -> list[str]:
        return [symbol for symbol in symbols if lower_val <= self.get(symbol, offset) <= upper_val]
    

    def surround_1(self, symbols: list[str]) -> dict:
        if len(symbols) == 0: return {}
        vals = [self.get(symbol) for symbol in symbols]

        # shift if negative (optional, only if you need non-negative values)
        min_val = min(vals)
        if min_val < 0:
            vals = [v - min_val for v in vals]

        mean_val = sum(vals) / len(vals)  # same as np.mean(vals)
        return {symbols[i]: vals[i] / mean_val for i in range(len(symbols))}
            