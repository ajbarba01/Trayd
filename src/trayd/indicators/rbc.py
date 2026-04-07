from .indicator import Indicator

from trayd.data import OHLCV

import numpy as np


class RBC(Indicator):
    def __init__(
        self,
        window: int,
        price: OHLCV = OHLCV.CLOSE,
        log_returns: bool = True
    ):
        self.window = window
        self.price = price
        self.log_returns = log_returns

        super().__init__("RollingBetaCorr")


    def get_warmup_window(self) -> int:
        # returns need one extra bar
        return self.window + 1


    def _get_settings(self) -> list:
        return [self.window, self.price, self.log_returns]


    def compute(self):
        """
        Intentionally empty.
        Computed on-demand via get_beta / get_corr.
        """
        return


    def _get_aligned_returns(self, a_idx: int, b_idx: int) -> tuple[np.ndarray, np.ndarray]:
        """
        Returns aligned return series for two symbols.
        If alignment is impossible, returns (empty, empty).
        """
        t = self.historical.current_ts_idx
        w = self.window

        prices_a = self.historical.bar_data[
            a_idx,
            t - w : t + 1,
            self.price
        ]
        prices_b = self.historical.bar_data[
            b_idx,
            t - w : t + 1,
            self.price
        ]

        # Require both assets to have prices on the same timestamps
        valid = ~np.isnan(prices_a) & ~np.isnan(prices_b)

        # Need at least 2 prices to compute returns
        if np.count_nonzero(valid) < 2:
            return np.array([]), np.array([])

        prices_a = prices_a[valid]
        prices_b = prices_b[valid]

        if self.log_returns:
            r_a = np.diff(np.log(prices_a))
            r_b = np.diff(np.log(prices_b))
        else:
            r_a = np.diff(prices_a) / prices_a[:-1]
            r_b = np.diff(prices_b) / prices_b[:-1]

        return r_a, r_b


    def get_beta(self, asset: str, reference: str) -> float:
        if asset == reference:
            return 1.0

        a_idx = self.historical.symbol_index[asset]
        r_idx = self.historical.symbol_index[reference]

        r_a, r_m = self._get_aligned_returns(a_idx, r_idx)

        if len(r_a) == 0:
            return np.nan

        var_m = np.var(r_m, ddof=1)
        if var_m == 0 or np.isnan(var_m):
            return np.nan

        cov = np.cov(r_a, r_m, ddof=1)[0, 1]
        return cov / var_m


    def get_corr(self, first: str, second: str) -> float:
        if first == second:
            return 1.0

        f_idx = self.historical.symbol_index[first]
        s_idx = self.historical.symbol_index[second]

        r1, r2 = self._get_aligned_returns(f_idx, s_idx)

        if len(r1) == 0:
            return np.nan

        return np.corrcoef(r1, r2)[0, 1]
