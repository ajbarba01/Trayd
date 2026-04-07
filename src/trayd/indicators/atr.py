from .indicator import Indicator

from trayd.data import OHLCV

import numpy as np


class ATR(Indicator):
    def __init__(self, window: int):
        self.window = window
        super().__init__("ATR")

    def get_warmup_window(self) -> int:
        return self.window

    def _get_settings(self) -> list:
        return [self.window]

    def compute(self):
        # OHLCV data: shape = (symbols, timestamps, OHLCV)
        high = self.historical.bar_data[:, :, OHLCV.HIGH]
        low = self.historical.bar_data[:, :, OHLCV.LOW]
        close = self.historical.bar_data[:, :, OHLCV.CLOSE]

        n_symbols, n_bars = close.shape
        window = self.window

        # Previous close (shifted by 1)
        prev_close = np.roll(close, 1, axis=1)
        prev_close[:, 0] = close[:, 0]  # first bar has no prev close

        # True range
        tr = np.maximum(
            high - low,
            np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)),
        )

        # Mask NaNs early to prevent propagation
        tr = np.where(np.isnan(tr), 0, tr)

        # Cumulative sum for fast SMA
        csum = np.cumsum(tr, axis=1)
        # Compute ATR using cumsum (vectorized)
        atr = np.full_like(tr, np.nan)
        atr[:, window - 1 :] = (
            csum[:, window - 1 :]
            - np.pad(csum[:, :-window], ((0, 0), (1, 0)), "constant")
        ) / window

        # Restore NaN for positions where window contained any original NaNs
        # This ensures we only produce ATR once a full valid window exists
        nan_mask = np.isnan(high) | np.isnan(low) | np.isnan(close)
        for t in range(window - 1, n_bars):
            mask = np.any(nan_mask[:, t - window + 1 : t + 1], axis=1)
            atr[:, t][mask] = np.nan

        # Store in indicator data
        self.indicator_data[:, self.key, :] = atr
