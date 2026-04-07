from .indicator import Indicator

from trayd.data import OHLCV

import pandas as pd
import numpy as np


class SMA(Indicator):
    def __init__(self, window: int, price: OHLCV = OHLCV.CLOSE):
        self.window = window
        self.price = price

        super().__init__("SMA")


    def get_warmup_window(self) -> int:
        return self.window


    def _get_settings(self) -> list:
        return [self.window, self.price]
    

    def compute(self):
        values = self.historical.bar_data[:, :, self.price]
        w = self.window
        num_symbols, num_timestamps = values.shape

        out = np.full((num_symbols, num_timestamps), np.nan, dtype=np.float64)
        csum = np.nancumsum(values, axis=1)

        # Correct: first valid SMA at index w-1
        out[:, w-1:] = (csum[:, w-1:] - np.pad(csum[:, :-w], ((0,0),(1,0)), 'constant')) / w

        self.indicator_data[:, self.key, :] = out
