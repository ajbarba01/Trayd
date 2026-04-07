from .indicator import Indicator

from trayd.data import OHLCV

import numpy as np


class OCMA(Indicator):
    """
    Overnight Change Moving Average (Open[t] vs Close[t-1]),
    forward-shifted to align with systems that auto-lag indicators.
    """

    def __init__(self, window: int):
        self.window = window
        super().__init__("OCMA")

    def get_warmup_window(self) -> int:
        # previous close + rolling window + forward shift
        return self.window + 1

    def _get_settings(self) -> list:
        return [self.window]

    def compute(self):
        opens = self.historical.bar_data[:, :, OHLCV.OPEN]
        closes = self.historical.bar_data[:, :, OHLCV.CLOSE]

        num_symbols, num_timestamps = opens.shape

        overnight = np.full_like(opens, np.nan, dtype=np.float64)
        overnight[:, 1:] = (opens[:, 1:] - closes[:, :-1]) / closes[:, :-1]

        w = self.window
        csum = np.nancumsum(overnight, axis=1)

        ocma = np.full_like(opens, np.nan, dtype=np.float64)

        # rolling mean (correct alignment)
        ocma[:, w:] = (csum[:, w:] - csum[:, :-w]) / w

        # forward shift to counter system-wide auto-lag
        ocma = np.roll(ocma, 1, axis=1)
        ocma[:, 0] = np.nan

        self.indicator_data[:, self.key, :] = ocma
