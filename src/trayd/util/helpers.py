import numpy as np

import math
import statistics

from datetime import datetime, time

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
    
def floor_cent(amount: float):
    return math.floor(amount * 100) / 100

def ceil_cent(amount: float):
    return math.ceil(amount * 100) / 100


def wrap_color(to_wrap: float, value: float, zero: float = 0, flip: bool = False) -> str:

    if flip:
        color = RED if value > zero else GREEN if value < zero else YELLOW
    else:
        color = GREEN if value > zero else RED if value < zero else YELLOW

    return f"{color}{to_wrap}{RESET}"


def fmt(amount, decimals: int = 2):
    s = f"{amount:,.{decimals}f}"
    return s.rstrip("0").rstrip(".")


def format_float(value: float, effective_zero: float = 0, decimal_places: float = 2, flip: bool = False):
    return wrap_color(fmt(value, decimal_places), value, zero=effective_zero, flip=flip)


def format_USD(amount: float, decimal_places: int = 2):
    return wrap_color("$" + fmt(amount, decimal_places), amount)


def format_percent(value: float, decimal_places: int = 2):
    return wrap_color(fmt(value * 100, decimal_places) + "%", value)


def format_multiplier(value: float):
    return wrap_color(fmt(value) + "x", value)


def print_numbered_list(str_list: list[str]):
    for i, text in enumerate(str_list):
        print(f"    {i + 1}. {text}")


def print_dashed_list(str_list: list[str]):
    for i, text in enumerate(str_list):
        print(f"    - {text}")


def print_bullet_list(str_list: list[str]):
    for i, text in enumerate(str_list):
        print(f"    • {text}")


def mean(list: list):
    if len(list) == 0:
        return -1
    return statistics.mean(list)


def stdev(list: list):
    if len(list) <= 1:
        return -1
    return statistics.stdev(list)


def percent_improvement(initial: float, final: float) -> str:
    improvement = (final / initial - 1)
    return format_percent(improvement)


def upwards_slippage(slippage_percent: float, price: float) -> float:
    return price * (1 + slippage_percent / 100)


def downwards_slippage(slippage_percent: float, price: float) -> float:
    return price * (1 - slippage_percent / 100)


def max_drawdown(values: list[float]) -> float:
    if not values:
        return 0.0

    peak = values[0]
    max_dd = 0.0

    for val in values:
        if val > peak:
            peak = val
        drawdown = (peak - val) / peak
        if drawdown > max_dd:
            max_dd = drawdown

    return -max_dd


def max_single_day_loss(values: list[float]) -> float:
    """
    Returns the largest loss between two consecutive values
    as a positive fraction (e.g. 0.05 = -5% day).
    """
    if len(values) < 2:
        return 0.0

    max_loss = 0.0

    for prev, curr in zip(values[:-1], values[1:]):
        if prev <= 0:
            continue  # avoid division by zero / invalid equity

        loss = (prev - curr) / prev
        if loss > max_loss:
            max_loss = loss

    return max_loss


def calculate_sharpe(portfolio_values: list[float], annual_risk_free: float = 0.0):
    vals = np.array(portfolio_values)
    daily_returns = vals[1:] / vals[:-1] - 1
    daily_rf = (1 + annual_risk_free)**(1/252) - 1  # convert annual RF to daily
    sharpe = (np.mean(daily_returns - daily_rf)) / np.std(daily_returns, ddof=1) * np.sqrt(252)
    return sharpe

def annualized_risk_adjusted_return(portfolio_values: list[float], annual_risk_free: float = 0.03):
    vals = np.array(portfolio_values)
    daily_returns = vals[1:] / vals[:-1] - 1
    n_days = len(daily_returns)
    
    # Annualized return
    total_return = vals[-1] / vals[0] - 1
    annualized_return = (1 + total_return) ** (252 / n_days) - 1
    
    # Annualized volatility
    annualized_vol = np.std(daily_returns, ddof=1) * np.sqrt(252)
    
    # Annualized Sharpe ratio
    daily_rf = (1 + annual_risk_free)**(1/252) - 1
    sharpe = (np.mean(daily_returns - daily_rf)) / np.std(daily_returns, ddof=1) * np.sqrt(252)
    
    # Risk-adjusted return
    risk_adjusted_return = annual_risk_free + sharpe * annualized_vol
    
    return risk_adjusted_return


def SMA(values: list[float], period: int) -> list[float]:
    """
    Calculate the Simple Moving Average (SMA) of a list of values.
    Returns a list of same length, with 0 for indices where SMA is undefined.
    """
    if period <= 0:
        raise ValueError("Period must be > 0")
    sma = [0.0] * len(values)
    for i in range(period - 1, len(values)):
        sma[i] = sum(values[i - period + 1:i + 1]) / period
    return sma


def EMA(values: list[float], period: int) -> list[float]:
    """
    Calculate the Exponential Moving Average (EMA) of a list of values.
    Returns a list of same length, with 0 for indices where EMA is undefined.
    """
    if period <= 0:
        raise ValueError("Period must be > 0")
    ema = [0.0] * len(values)
    multiplier = 2 / (period + 1)

    if len(values) >= period:
        initial_sma = sum(values[:period]) / period
        ema[period - 1] = initial_sma
        for i in range(period, len(values)):
            ema[i] = (values[i] - ema[i - 1]) * multiplier + ema[i - 1]
    return ema


def is_intraday(current_time: time):
    return time(9, 30) <= current_time < time(16, 0)


def equity_to_returns(equity: list[float]):
    vals = np.asarray(equity)
    return vals[1:] / vals[:-1] - 1

def get_correlation(equity_a: list[float], equity_b: list[float]):
    ra = equity_to_returns(equity_a)
    rb = equity_to_returns(equity_b)

    n = min(len(ra), len(rb))
    ra = ra[-n:]
    rb = rb[-n:]

    return np.corrcoef(ra, rb)[0, 1]


def get_beta(equity_strategy, equity_market):
    rs = equity_to_returns(equity_strategy)
    rm = equity_to_returns(equity_market)

    n = min(len(rs), len(rm))
    rs = rs[-n:]
    rm = rm[-n:]

    cov = np.cov(rs, rm)[0, 1]
    var = np.var(rm)

    return cov / var


def surround_1(values: dict) -> dict:
    """
    Normalize values so that:
      - All outputs are non-negative
      - Mean(output) == 1
      - Sum(output) == len(values)

    Returns an empty dict if input is empty.
    """
    if not values:
        return {}

    keys = list(values.keys())
    vals = list(values.values())

    # Shift if any values are negative
    min_val = min(vals)
    if min_val < 0:
        vals = [v - min_val for v in vals]

    total = sum(vals)
    if total == 0:
        # Degenerate case: all inputs equal (or all zero after shift)
        return {k: 1.0 for k in keys}

    mean_val = total / len(vals)

    return {
        keys[i]: vals[i] / mean_val
        for i in range(len(keys))
    }
