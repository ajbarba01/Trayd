from .indicator import Indicator
from .sma import SMA

from trayd.data import OHLCV

import pandas as pd


class TEST(Indicator):
    def __init__(self, window: int, price: OHLCV = OHLCV.CLOSE):
        self.window = window
        self.price = price

        super().__init__("TEST")

        self.warmup_window = window

    def get_prereqs(self):
        return [SMA(self.window, self.price)]

    def _get_settings(self):
        return [self.window, self.price]

    def compute(self):
        pass
