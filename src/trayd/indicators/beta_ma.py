from .indicator import Indicator

from trayd.data import OHLCV
import numpy as np

class BetaMA(Indicator):
    """
    Rolling Beta moving average to a reference symbol.
    """

    def __init__(self, reference_symbol: str, window: int, price: OHLCV = OHLCV.CLOSE):
        self.reference_symbol = reference_symbol
        self.window = window
        self.price = price
        super().__init__("BetaMA")

    def get_warmup_window(self) -> int:
        return self.window

    def _get_settings(self) -> list:
        return [self.reference_symbol, self.window, self.price]

    def compute(self):
        values = self.historical.bar_data[:, :, self.price]  # (symbols, timestamps)
        num_symbols, num_timestamps = values.shape

        ref_idx = self.historical.symbol_index[self.reference_symbol]
        ref_vals = values[ref_idx, :]

        # compute returns (close-to-close)
        returns = np.empty_like(values)
        returns[:, 1:] = values[:, 1:] / values[:, :-1] - 1
        returns[:, 0] = np.nan

        ref_returns = np.empty_like(ref_vals)
        ref_returns[1:] = ref_vals[1:] / ref_vals[:-1] - 1
        ref_returns[0] = np.nan

        beta = np.full_like(values, np.nan, dtype=np.float64)

        # vectorized rolling beta using cumulative sums
        # cumulative sums and sums of squares for reference
        cumsum_ref = np.nancumsum(ref_returns)
        cumsum_ref_sq = np.nancumsum(ref_returns**2)

        for t in range(self.window, num_timestamps):
            # slice window
            window_ret = returns[:, t - self.window:t]
            window_ref = ref_returns[t - self.window:t]

            # mean subtraction
            mean_window = np.nanmean(window_ret, axis=1, keepdims=True)
            mean_ref = np.nanmean(window_ref)

            cov = np.nansum((window_ret - mean_window) * (window_ref - mean_ref), axis=1) / (self.window - 1)
            var = np.nanvar(window_ref, ddof=1)

            beta[:, t] = cov / var if var != 0 else np.nan

        # forward shift to match your system's auto-lag
        beta = np.roll(beta, 1, axis=1)
        beta[:, 0] = np.nan

        self.indicator_data[:, self.key, :] = beta
