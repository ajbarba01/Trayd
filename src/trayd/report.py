import time

import matplotlib.pyplot as plt
import pandas as pd

from .portfolio import Portfolio

from trayd.data import HistoricalData

from trayd.util.helpers import (
    format_percent,
    format_USD,
    percent_improvement,
    mean,
    max_drawdown,
    max_single_day_loss,
    annualized_risk_adjusted_return,
    calculate_sharpe,
    format_multiplier,
    format_float,
    print_numbered_list,
    print_dashed_list,
    get_correlation,
    get_beta,
)


class Report:

    width: int = 80
    algos: dict[str, any] = {}
    equity_curves: dict[str, list] = {}
    references: dict[str, list] = {}
    correlations: list[str] = []
    base: str = None
    performances: dict[str, list] = {}
    portfolio: Portfolio = None
    historical: HistoricalData = None
    algo = None

    @staticmethod
    def initialize(portfolio: Portfolio, historical: HistoricalData, algo):
        Report.portfolio = portfolio
        Report.historical = historical
        Report.algo = algo

    @staticmethod
    def add_equity_curve(algo: any, base: bool = True):
        Report.algos[algo.name] = algo
        Report.equity_curves[algo.name] = []
        if base:
            Report.base = algo.name

    @staticmethod
    def add_reference(symbol: str, correlate: bool = False):
        Report.references[symbol] = []
        if correlate:
            Report.correlations.append(symbol)

    @staticmethod
    def set_performance(name: str, values: list):
        Report.performances[name] = values

    @staticmethod
    def new_day(daily: HistoricalData):
        for symbol in Report.references:
            Report.references[symbol].append(daily.get_close(symbol))

        for algo_name, algo in Report.algos.items():
            Report.equity_curves[algo_name].append(algo.portfolio.equity)

    @staticmethod
    def print_report(
        initial: float,
        final: float,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp,
        avg_exposure: float,
        start_load: float,
        end_load: float,
        total_bars: int,
    ):
        # Format end date
        start_date_formatted = start_ts.strftime("%B %d, %Y")
        end_date_formatted = end_ts.strftime("%B %d, %Y")

        # Compute days
        days = (end_ts - start_ts).days

        # Annualized return
        annualized_return = (final / initial) ** (365 / days) - 1

        portfolio_values = list(Report.equity_curves.values())[0]

        print(f"".center(80, "-"))
        print()
        print(f"Report for {Report.algo.name}".center(80))
        print()
        print(f"{start_date_formatted} -> {end_date_formatted}".center(80))
        print()
        print(
            f"Indices Used: {",".join([idx.index_name for idx in Report.algo.indices])}"
        )
        # print(f"Max Exposure: {format_multiplier(Report.portfolio.max_exposure)}")
        print(
            f"Effective Leverage: {format_multiplier(Report.portfolio.max_exposure)} of {format_multiplier(Report.portfolio.leverage)} (Deprecated)"
        )
        print(f"Initial Value: {format_USD(initial)}")
        print(
            f"Final Value: {format_USD(final)} ({percent_improvement(initial, final)})"
        )
        print(f"Annualized Return: {format_percent(annualized_return)}")
        print(
            f"Risk-adjusted Return: {format_percent(annualized_risk_adjusted_return(portfolio_values))}"
        )
        print(f"Time-Weighted Exposure: {format_percent(avg_exposure)}")
        print(f"Max Drawdown: {format_percent(max_drawdown(portfolio_values))}")
        print(
            f"Max Single Day Loss: {format_percent(max_single_day_loss(portfolio_values))}"
        )
        print(
            f"Sharpe Ratio: {format_float(calculate_sharpe(portfolio_values), 1)}"
        )
        print(f"Trades: {Report.portfolio.num_trades}")
        print(
            f"Slippage Percentage: {format_percent(Report.portfolio.slippage_percent / 100, 3)}"
        )
        print(f"Total Slippage: {format_USD(-Report.portfolio.total_slippage)}")

        if Report.portfolio.total_margin_interest != 0:
            print(
                f"Total Margin Interest: {format_USD(-Report.portfolio.total_margin_interest)}"
            )

        Report.print_correlations()
        Report.print_profits()
        Report.print_positions()
        print()
        print(
            f"Load: {(end_load - start_load):.2f} s, Runtime: {(time.time() - end_load):.2f} s, {total_bars} bars".center(
                80
            )
        )
        print()
        print("".center(80, "-"))

    @staticmethod
    def print(*args, **kwargs):
        print(*args, **kwargs)

    @staticmethod
    def print_correlations():
        if not Report.base or len(Report.correlations) == 0:
            return

        print(f"\nCORRELATIONS ({Report.base})")
        base_curve = Report.equity_curves[Report.base]
        corr_list = [
            f"{reference}: {format_float(get_correlation(Report.references[reference], base_curve), 0.3, flip=True)} (corr), {format_float(get_beta(Report.references[reference], base_curve), 0.1, flip=True)} (beta)"
            for reference in Report.correlations
        ]
        print_dashed_list(corr_list)

    @staticmethod
    def print_profits():
        print(
            f"\nREALIZED PROFITS BY COMPANY (Total {format_USD(sum(list(Report.portfolio.symbol_profits.values())))}):"
        )
        sorted_symbols = dict(
            sorted(
                Report.portfolio.symbol_profits.items(),
                key=lambda item: item[1],
            )
        )
        symbol_list = [
            f"{symbol}: {format_USD(profit)}"
            for symbol, profit in sorted_symbols.items()
        ]
        print_dashed_list(symbol_list)

    @staticmethod
    def print_positions():
        if len(Report.portfolio.positions) == 0:
            return
        print(f"\nUNREALIZED POSITIONS ({len(Report.portfolio.positions)}):")
        symbol_list = [
            f"{symbol}: {position.entry_time.date()} @ {format_USD(position.last_known_price * position.shares)}"
            for symbol, position in Report.portfolio.positions.items()
        ]
        print_numbered_list(symbol_list)

    @staticmethod
    def check_valid() -> bool:
        valid = False
        for curve in Report.equity_curves.values():
            if not curve:
                continue
            ref = curve[0]
            for value in curve:
                if ref != value:
                    valid = True

        return valid

    @staticmethod
    def show_plots(initial: float):
        if not Report.check_valid():
            return

        # Determine number of subplots: 2 (equity + performance)
        fig, (ax1, ax2) = plt.subplots(
            2,
            1,
            figsize=(12, 10),
            sharex=True,
            gridspec_kw={"height_ratios": [2, 1]},
        )

        # --- Top plot: Equity Curves ---
        all_curves = Report.equity_curves.copy()
        for reference, values in Report.references.items():
            if not values:
                continue
            mod = initial / values[0]
            all_curves[reference] = [value * mod for value in values]

        for name, values in all_curves.items():
            ax1.plot(values, label=name)
        ax1.set_ylabel("Equity Value ($)")
        ax1.set_title("Equity Curves Comparison")
        ax1.grid(True)
        ax1.legend()

        # --- Bottom plot: Performances ---
        if Report.performances:
            for name, values in Report.performances.items():
                ax2.plot(values, label=name)
            ax2.set_ylabel("Performance Metric")
            ax2.set_xlabel("Time Step")
            ax2.set_title("Performance Metrics")
            ax2.grid(True)
            ax2.legend()
        else:
            ax2.set_visible(False)  # hide bottom plot if no performances

        plt.tight_layout()
        plt.show()
