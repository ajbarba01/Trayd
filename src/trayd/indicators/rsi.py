from .indicator import Indicator

from trayd.data import OHLCV

import numpy as np


class RSI(Indicator):
    def __init__(self, period: int = 14, price: OHLCV = OHLCV.CLOSE):
        self.period = period
        self.price = price
        super().__init__("RSI")

    def get_warmup_window(self) -> int:
        return self.period

    def _get_settings(self) -> list:
        return [self.period, self.price]

    def compute(self):
        prices = self.historical.bar_data[:, :, self.price]
        n_symbols, n_ts = prices.shape
        p = self.period

        out = np.full((n_symbols, n_ts), np.nan)

        deltas = np.diff(prices, axis=1)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = np.full((n_symbols, n_ts), np.nan)
        avg_loss = np.full((n_symbols, n_ts), np.nan)

        avg_gain[:, p] = np.nanmean(gains[:, :p], axis=1)
        avg_loss[:, p] = np.nanmean(losses[:, :p], axis=1)

        for t in range(p + 1, n_ts):
            avg_gain[:, t] = (
                avg_gain[:, t - 1] * (p - 1) + gains[:, t - 1]
            ) / p
            avg_loss[:, t] = (
                avg_loss[:, t - 1] * (p - 1) + losses[:, t - 1]
            ) / p

        # Compute RSI safely
        rs = np.full((n_symbols, n_ts), np.nan)

        valid = avg_loss > 0
        rs[valid] = avg_gain[valid] / avg_loss[valid]

        # avg_loss == 0 → RSI = 100
        out[avg_loss == 0] = 100
        out[valid] = 100 - (100 / (1 + rs[valid]))

        self.indicator_data[:, self.key, :] = out
