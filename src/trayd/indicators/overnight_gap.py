from .indicator import Indicator
from .atr import ATR

from trayd.data import OHLCV

import numpy as np


class OvernightGap(Indicator):
    """
    Overnight gap normalized by ATR:
    (Open_t - Close_{t-1}) / ATR_{t-1}
    """

    def __init__(self, atr_window: int = 2):
        self.atr_window = atr_window
        super().__init__("OvernightGapATR")

    def get_warmup_window(self) -> int:
        # Need ATR warmup + 1 prior close
        return self.atr_window + 1

    def _get_settings(self) -> list:
        return [self.atr_window]

    def get_prereqs(self):
        # Require ATR computed on the same HistoricalData
        return [ATR(self.atr_window)]

    def compute(self):
        opens = self.historical.bar_data[:, :, OHLCV.OPEN]
        closes = self.historical.bar_data[:, :, OHLCV.CLOSE]

        atr = self.indicator_data[:, self.dependencies[0].key, :]

        num_symbols, num_ts = opens.shape
        out = np.full((num_symbols, num_ts), np.nan, dtype=np.float64)

        # Step 1: compute the raw overnight gap at t
        # gap[t] = (open[t] - close[t-1]) / atr[t-1]
        raw = np.full((num_symbols, num_ts), np.nan, dtype=np.float64)

        prev_close = closes[:, :-1]
        today_open = opens[:, 1:]
        prev_atr = atr[:, :-1]

        valid = (
            ~np.isnan(prev_close)
            & ~np.isnan(today_open)
            & ~np.isnan(prev_atr)
            & (prev_atr > 0)
        )

        raw[:, 1:][valid] = (today_open[valid] - prev_close[valid]) / prev_atr[
            valid
        ]

        # Step 2: shift forward by one so algorithm reads it on the correct day
        out[:, 1:] = raw[:, :-1]

        self.indicator_data[:, self.key, :] = out
