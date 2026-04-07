from .indicator import Indicator

from trayd.data import OHLCV

import pandas as pd
import numpy as np


class ATH(Indicator):
    def __init__(self, window: int, price: OHLCV = OHLCV.CLOSE):
        self.window = window
        self.price = price
        super().__init__("ATH")

    def get_warmup_window(self) -> int:
        return self.window

    def _get_settings(self) -> list:
        return [self.window, self.price]

    def compute(self):
        values = self.historical.bar_data[:, :, self.price]
        w = self.window
        num_symbols, num_timestamps = values.shape

        out = np.full((num_symbols, num_timestamps), np.nan, dtype=np.float64)

        # Rolling max: first valid ATH at index w-1
        for t in range(w - 1, num_timestamps):
            out[:, t] = np.nanmax(values[:, t - w + 1 : t + 1], axis=1)

        self.indicator_data[:, self.key, :] = out


class ATL(Indicator):
    def __init__(self, window: int, price: OHLCV = OHLCV.CLOSE):
        self.window = window
        self.price = price
        super().__init__("ATL")

    def get_warmup_window(self) -> int:
        return self.window

    def _get_settings(self) -> list:
        return [self.window, self.price]

    def compute(self):
        values = self.historical.bar_data[:, :, self.price]
        w = self.window
        num_symbols, num_timestamps = values.shape

        out = np.full((num_symbols, num_timestamps), np.nan, dtype=np.float64)

        # Rolling min: first valid ATL at index w-1
        for t in range(w - 1, num_timestamps):
            out[:, t] = np.nanmin(values[:, t - w + 1 : t + 1], axis=1)

        self.indicator_data[:, self.key, :] = out