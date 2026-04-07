from .indicator import Indicator

from trayd.data import OHLCV

import numpy as np


class ADX(Indicator):
    def __init__(self, period: int = 14):
        self.period = period
        super().__init__("ADX")

    def get_warmup_window(self) -> int:
        # First valid ADX value appears at index 2p
        return self.period * 2 + 1

    def _get_settings(self) -> list:
        return [self.period]

    def compute(self):
        high = self.historical.bar_data[:, :, OHLCV.HIGH]
        low = self.historical.bar_data[:, :, OHLCV.LOW]
        close = self.historical.bar_data[:, :, OHLCV.CLOSE]

        n_symbols, n_ts = high.shape
        p = self.period
        eps = 1e-12

        # ----------------------------
        # True Range & Directional Movement
        # ----------------------------
        up = high[:, 1:] - high[:, :-1]
        down = low[:, :-1] - low[:, 1:]

        plus_dm = np.zeros((n_symbols, n_ts))
        minus_dm = np.zeros((n_symbols, n_ts))

        plus_dm[:, 1:] = np.where((up > down) & (up > 0), up, 0)
        minus_dm[:, 1:] = np.where((down > up) & (down > 0), down, 0)

        tr = np.zeros((n_symbols, n_ts))
        tr[:, 1:] = np.nanmax(
            np.stack([
                high[:, 1:] - low[:, 1:],
                np.abs(high[:, 1:] - close[:, :-1]),
                np.abs(low[:, 1:] - close[:, :-1])
            ]),
            axis=0,
            initial=0  # <- prevents all-NaN warnings
        )

        # ----------------------------
        # Wilder smoothing
        # ----------------------------
        atr = np.full((n_symbols, n_ts), np.nan)
        plus_sm = np.full((n_symbols, n_ts), np.nan)
        minus_sm = np.full((n_symbols, n_ts), np.nan)

        # Seed smoothing with sum of first p periods
        atr[:, p] = np.nansum(tr[:, 1:p+1], axis=1)
        plus_sm[:, p] = np.nansum(plus_dm[:, 1:p+1], axis=1)
        minus_sm[:, p] = np.nansum(minus_dm[:, 1:p+1], axis=1)

        for t in range(p + 1, n_ts):
            atr[:, t] = atr[:, t-1] - (atr[:, t-1] / p) + tr[:, t]
            plus_sm[:, t] = plus_sm[:, t-1] - (plus_sm[:, t-1] / p) + plus_dm[:, t]
            minus_sm[:, t] = minus_sm[:, t-1] - (minus_sm[:, t-1] / p) + minus_dm[:, t]

        # ----------------------------
        # DI and DX (safe)
        # ----------------------------
        atr_safe = np.where(atr == 0, eps, atr)

        plus_di = 100 * plus_sm / atr_safe
        minus_di = 100 * minus_sm / atr_safe

        di_sum = plus_di + minus_di
        di_sum = np.where(di_sum == 0, eps, di_sum)

        dx = 100 * np.abs(plus_di - minus_di) / di_sum

        # ----------------------------
        # ADX initialization & smoothing (safe)
        # ----------------------------
        adx = np.full((n_symbols, n_ts), np.nan)

        slice_dx = dx[:, p+1:2*p+1]
        adx[:, 2 * p] = np.where(
            np.all(np.isnan(slice_dx), axis=1),
            0,  # fallback when all NaNs
            np.nanmean(slice_dx, axis=1)
        )

        for t in range(2 * p + 1, n_ts):
            adx[:, t] = ((adx[:, t-1] * (p - 1)) + dx[:, t]) / p

        self.indicator_data[:, self.key, :] = adx
