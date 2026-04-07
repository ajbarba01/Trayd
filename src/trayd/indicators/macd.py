import numpy as np
from .indicator import Indicator
from .ema import EMA

from trayd.data import OHLCV


class MACDHistogram(Indicator):
    def __init__(
        self, fast: int = 12, slow: int = 26, signal: int = 9, price=OHLCV.CLOSE
    ):
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self.price = price

        super().__init__("MACDHistogram")

    def get_prereqs(self) -> list:
        # Add MACD and MACDSignal with the same parameters
        macd = MACD(fast=self.fast, slow=self.slow, price=self.price)
        macd_signal = MACDSignal(
            macd_fast=self.fast, macd_slow=self.slow, signal=self.signal
        )
        return [macd, macd_signal]

    def get_warmup_window(self) -> int:
        # Histogram is valid after MACD and Signal are ready
        return self.dependencies[1].get_warmup_window()

    def _get_settings(self) -> list:
        return [self.fast, self.slow, self.signal]

    def compute(self):
        # Use dependencies to get correct keys
        macd_values = self.indicator_data[:, self.dependencies[0].key, :]
        signal_values = self.indicator_data[:, self.dependencies[1].key, :]

        # Histogram = MACD - MACDSignal
        self.indicator_data[:, self.key, :] = macd_values - signal_values

    def just_crossed_bullish(
        self, symbol: str, offset: int = 0, only_above: float = 0.0
    ):
        macd = self.dependencies[0]
        signal = self.dependencies[1]

        curr_macd = macd.get(symbol, offset)
        curr_signal = signal.get(symbol, offset)

        prev_macd = macd.get(symbol, offset - 1)
        prev_signal = signal.get(symbol, offset - 1)

        above_line = curr_macd > only_above and curr_signal > only_above
        just_crossed = prev_macd < prev_signal and curr_macd > curr_signal
        just_crossed_bullish = above_line and just_crossed

        return just_crossed_bullish

    def just_crossed_bearish(
        self, symbol: str, offset: int = 0, only_below: float = 0.0
    ):
        macd = self.dependencies[0]
        signal = self.dependencies[1]

        curr_macd = macd.get(symbol, offset)
        curr_signal = signal.get(symbol, offset)

        prev_macd = macd.get(symbol, offset - 1)
        prev_signal = signal.get(symbol, offset - 1)

        # Check that current values are below threshold (optional)
        below_line = curr_macd < only_below and curr_signal < only_below
        just_crossed = prev_macd > prev_signal and curr_macd < curr_signal
        just_crossed_bearish = below_line and just_crossed

        return just_crossed_bearish

    def just_exited_bullish(self, symbol: str, offset: int = 0):
        macd = self.dependencies[0]
        signal = self.dependencies[1]

        curr_macd = macd.get(symbol, offset)
        curr_signal = signal.get(symbol, offset)

        prev_macd = macd.get(symbol, offset - 1)
        prev_signal = signal.get(symbol, offset - 1)

        # Fires only on the bar the histogram goes from positive to negative
        just_exited = prev_macd >= prev_signal and curr_macd < curr_signal

        return just_exited


class MACD(Indicator):
    def __init__(
        self, fast: int = 12, slow: int = 26, price: OHLCV = OHLCV.CLOSE
    ):
        self.fast = fast
        self.slow = slow
        self.price = price

        # Prereq EMAs
        self.ema_fast = EMA(fast, price)
        self.ema_slow = EMA(slow, price)

        super().__init__("MACD")

    def get_prereqs(self) -> list:
        return [self.ema_fast, self.ema_slow]

    def get_warmup_window(self) -> int:
        return max(self.fast, self.slow)

    def _get_settings(self) -> list:
        return [self.fast, self.slow, self.price]

    def compute(self):
        ema_fast = self.indicator_data[:, self.ema_fast.key, :]
        ema_slow = self.indicator_data[:, self.ema_slow.key, :]

        self.indicator_data[:, self.key, :] = ema_fast - ema_slow


class MACDSignal(Indicator):
    def __init__(
        self, macd_fast: int = 12, macd_slow: int = 26, signal: int = 9
    ):
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.signal = signal

        # MACD prereq
        self.macd = MACD(macd_fast, macd_slow)

        super().__init__("MACDSignal")

    def get_prereqs(self) -> list:
        return [self.macd]

    def get_warmup_window(self) -> int:
        # MACD warmup + signal period
        return self.macd_slow + self.signal

    def _get_settings(self) -> list:
        return [self.macd_fast, self.macd_slow, self.signal]


class MACDSignal(Indicator):
    """
    MACD Signal line indicator — computes the EMA of the MACD values.
    Handles NaNs at the start and ensures proper warmup.
    """

    def __init__(
        self, macd_fast: int = 12, macd_slow: int = 26, signal: int = 9
    ):
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.signal = signal

        super().__init__("MACDSignal")

    def get_prereqs(self) -> list:
        return [MACD(self.macd_fast, self.macd_slow)]

    def get_warmup_window(self) -> int:
        # Must wait for MACD warmup + signal length
        return self.macd_slow + self.signal

    def _get_settings(self) -> list:
        return [self.macd_fast, self.macd_slow, self.signal]

    def compute(self):
        # Fetch MACD values
        macd_values = self.indicator_data[:, self.dependencies[0].key, :]
        num_symbols, num_timestamps = macd_values.shape
        alpha = 2 / (self.signal + 1)

        # Prepare output
        signal_line = np.full_like(macd_values, np.nan, dtype=np.float64)

        # Compute EMA for each symbol separately
        for s in range(num_symbols):
            # Find first valid MACD bars
            valid_idx = np.where(~np.isnan(macd_values[s]))[0]
            if len(valid_idx) < self.signal:
                continue  # Not enough bars to start EMA

            start = valid_idx[0] + self.signal - 1
            # Initialize SMA over first 'signal' valid MACD bars
            signal_line[s, start] = np.nanmean(
                macd_values[s, valid_idx[0] : valid_idx[0] + self.signal]
            )

            # Recursive EMA
            for t in range(start + 1, num_timestamps):
                if np.isnan(macd_values[s, t]):
                    # If MACD missing, carry previous EMA forward
                    signal_line[s, t] = signal_line[s, t - 1]
                else:
                    signal_line[s, t] = (
                        alpha * macd_values[s, t]
                        + (1 - alpha) * signal_line[s, t - 1]
                    )

        # Store in indicator data
        self.indicator_data[:, self.key, :] = signal_line
