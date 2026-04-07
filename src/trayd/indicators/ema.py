from .indicator import Indicator

from trayd.data import OHLCV
import numpy as np


class EMA(Indicator):
    def __init__(self, window: int, price: OHLCV = OHLCV.CLOSE):
        self.window = window
        self.price = price
        super().__init__("EMA")

    def get_warmup_window(self) -> int:
        return self.window

    def _get_settings(self) -> list:
        return [self.window, self.price]

    def compute(self):
        values = self.historical.bar_data[:, :, self.price]
        w = self.window
        alpha = 2 / (w + 1)

        num_symbols, num_timestamps = values.shape
        ema = np.full((num_symbols, num_timestamps), np.nan, dtype=np.float64)

        # --- Safe initialization per symbol ---
        for s in range(num_symbols):
            window_slice = values[s, :w]

            if np.all(np.isnan(window_slice)):
                continue  # symbol has no data yet

            ema[s, w - 1] = np.nanmean(window_slice)

            # Recursive EMA
            for t in range(w, num_timestamps):
                price = values[s, t]
                prev = ema[s, t - 1]

                if np.isnan(price):
                    ema[s, t] = prev
                else:
                    ema[s, t] = alpha * price + (1 - alpha) * prev

        self.indicator_data[:, self.key, :] = ema
