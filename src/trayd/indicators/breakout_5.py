from .indicator import Indicator

from trayd.data import OHLCV

import numpy as np


class Breakout5(Indicator):
    def __init__(self, lookback: int = 5, price: OHLCV = OHLCV.CLOSE):
        self.lookback = lookback
        self.price = price

        super().__init__("Breakout5")


    def get_warmup_window(self) -> int:
        return self.lookback


    def _get_settings(self) -> list:
        return [self.lookback, self.price]


    def compute(self):
        values = self.historical.bar_data[:, :, self.price]
        n_symbols, n_timestamps = values.shape
        lb = self.lookback

        out = np.zeros((n_symbols, n_timestamps), dtype=np.int8)

        for t in range(lb, n_timestamps):
            window = values[:, t - lb:t]

            prev_max = np.nanmax(window, axis=1)
            prev_min = np.nanmin(window, axis=1)
            curr = values[:, t]

            out[curr > prev_max, t] = 1
            out[curr < prev_min, t] = -1

        self.indicator_data[:, self.key, :] = out


    def is_five_bar_high(self, symbol: str):
        return self.get(symbol) == 1
    

    def is_five_bar_low(self, symbol: str):
        return self.get(symbol) == -1
