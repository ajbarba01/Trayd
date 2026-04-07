from .indicator import Indicator

from trayd.data import OHLCV

import numpy as np


class Flag(Indicator):
    def __init__(
        self,
        window: int,
        std_threshold: float,
        slope_threshold: float,
    ):
        self.window = window
        self.std_threshold = std_threshold
        self.slope_threshold = slope_threshold
        super().__init__("Flag")

    def get_warmup_window(self) -> int:
        # Need window + 1 bars to form window percentage diffs
        return self.window + 1

    def _get_settings(self) -> list:
        return [self.window, self.std_threshold, self.slope_threshold]

    def compute(self):
        highs = self.historical.bar_data[:, :, OHLCV.HIGH]
        lows  = self.historical.bar_data[:, :, OHLCV.LOW]

        num_symbols, num_timestamps = highs.shape
        out = np.full((num_symbols, num_timestamps), np.nan, dtype=np.float64)

        w = self.window

        for t in range(w, num_timestamps):
            # window+1 bars → window pct diffs
            h_slice = highs[:, t - w : t + 1]
            l_slice = lows[:,  t - w : t + 1]

            # Percentage differences
            h_prev = h_slice[:, :-1]
            l_prev = l_slice[:, :-1]

            h_diff = (h_slice[:, 1:] - h_prev) / np.abs(h_prev)
            l_diff = (l_slice[:, 1:] - l_prev) / np.abs(l_prev)

            # Std deviation filter
            h_std = np.nanstd(h_diff, axis=1)
            l_std = np.nanstd(l_diff, axis=1)

            valid = (h_std <= self.std_threshold) & (l_std <= self.std_threshold)

            if not np.any(valid):
                continue

            # Slopes = mean percentage change
            h_slope = np.nanmean(h_diff, axis=1)
            l_slope = np.nanmean(l_diff, axis=1)

            # Direction + magnitude checks
            valid &= (
                (h_slope < 0) &                       # highs trending down
                (l_slope > 0) &                       # lows trending up
                (np.abs(h_slope) <= self.slope_threshold) &
                (np.abs(l_slope) <= self.slope_threshold)
            )

            if not np.any(valid):
                continue

            # Positive ratio
            out[valid, t] = np.abs(h_slope[valid] / l_slope[valid])

        self.indicator_data[:, self.key, :] = out
