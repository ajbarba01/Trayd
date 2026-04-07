from .indicator import Indicator

from trayd.data import OHLCV

import pandas as pd
import numpy as np


class ROC(Indicator):
    def __init__(self, window: int, price: OHLCV = OHLCV.CLOSE):
        self.window = window
        self.price = price

        super().__init__("ROC")


    def get_warmup_window(self) -> int:
        return self.window


    def _get_settings(self) -> list:
        return [self.window, self.price]
    

    def compute(self):
        values = self.historical.bar_data[:, :, self.price]
        w = self.window
        out = np.full_like(values, np.nan)

        # ROC = (current - lag) / lag
        out[:, w:] = (values[:, w:] - values[:, :-w]) / values[:, :-w]

        self.indicator_data[:, self.key, :] = out