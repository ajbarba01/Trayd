import matplotlib.pyplot as plt
import pandas as pd
import time

from .portfolio import Portfolio
from .report import Report

from trayd.algorithms import Algorithm
from trayd.data import HistoricalData, Granularity
from trayd.util import Logger, ProgressBar

from trayd.util.helpers import (
    format_USD,
    percent_improvement,
    format_percent,
    mean,
    max_drawdown,
    calculate_sharpe,
    annualized_risk_adjusted_return,
)


class Backtest:
    def __init__(
        self,
        start_date: str,
        end_date: str,
        algorithm: Algorithm,
        cash: float,
        using_intraday: bool = False,
        leverage: float = 1.0,
        margin_interest_rate: float = 0.0625,
        margin_maintenance: float = 0.3,
        max_exposure: float = 1.0,
    ):
        self.start_load_time = time.time()

        self.start_date = start_date
        self.end_date = end_date
        self.initial_cash = cash
        self.algorithm = algorithm
        self.using_intraday = using_intraday

        # Data
        self.daily = HistoricalData()
        self.historical = (
            HistoricalData(Granularity.INTRADAY)
            if using_intraday
            else self.daily
        )

        # Portfolio
        self.portfolio = Portfolio(
            self.historical,
            self.using_intraday,
            cash=cash,
            leverage=leverage,
            margin_interest_rate=margin_interest_rate,
            margin_maintenance=margin_maintenance,
            max_exposure=max_exposure,
        )

        # State
        self.current_day = None
        self.current_month = None

        self.last_ts = None
        self.exposure_time_sum = 0.0
        self.total_time = 0.0

        self.total_bars = 0
        self.should_show_plot = True
        self.end_load_time = None

        self.pbar = ProgressBar("Running Backtest", show_unit=False)

    # ==========================================================
    # Main Loop
    # ==========================================================

    def run(self):
        try:
            self._initialize()

            while not self.is_finished():
                self.total_bars += 1

                # ---- Advance time (ONLY PLACE TIME MOVES) ----
                if self.using_intraday:
                    self.historical.next()
                    self.pbar.next()
                else:
                    self.daily.next()

                self._accumulate_exposure()

                # ---- Milestones ----
                if self._check_new_day():
                    self._new_day()

                # ---- Strategy + Portfolio ----
                self.portfolio.next()
                self.algorithm.tick()

            self.algorithm.last_day()
            self.pbar.stop()
            self.algorithm.end()
            self.report()

        except KeyboardInterrupt:
            print("Keyboard Interrupt. Exiting")

    # ==========================================================
    # Time & Exposure
    # ==========================================================

    def _accumulate_exposure(self):
        ts = self._current_ts()

        if self.last_ts is not None:
            dt = (ts - self.last_ts).total_seconds()

            exposure = (
                self.portfolio.gross_value / self.portfolio.equity
                if self.portfolio.equity > 0
                else 0.0
            )

            self.exposure_time_sum += exposure * dt
            self.total_time += dt

        self.last_ts = ts

    def _current_ts(self):
        return (
            self.historical.current_ts
            if self.using_intraday
            else self.daily.current_ts
        )

    # ==========================================================
    # Termination
    # ==========================================================

    def is_finished(self) -> bool:
        if self.using_intraday:
            return self.historical.is_finished() or self.daily.is_finished()
        return self.daily.is_finished()

    # ==========================================================
    # Milestones
    # ==========================================================

    def _check_new_day(self) -> bool:
        ts = self._current_ts()

        if ts.month != self.current_month:
            self.current_month = ts.month
            self._new_month()

        if ts.day != self.current_day:
            return True

        return False

    def _new_day(self):
        # Sync daily data to intraday date
        if self.using_intraday:
            while self.daily.current_ts.normalize() < self.historical.current_ts.normalize():
                self.daily.next()

        ts = self._current_ts()
        self.current_day = ts.day

        for index in self.algorithm.indices:
            index.update_to(ts)

        # self.portfolio.apply_margin_interest()
        self.algorithm.new_day()
        self.portfolio.new_day()
        Report.new_day(self.daily)

    def _new_month(self):
        self.algorithm.new_month()

    # ==========================================================
    # Initialization
    # ==========================================================

    def _initialize(self):
        self.algorithm.initialize(self.historical, self.daily, self.portfolio)
        self.algorithm.start()

        Report.initialize(self.portfolio, self.historical, self.algorithm)
        Report.add_reference("SPY", correlate=True)
        Report.add_reference("OEF")
        Report.add_reference("IWM", correlate=True)

        self._initialize_indices()

        self.historical.add_window_padding(self.algorithm.window_padding)
        self.historical.load_all(
            self.algorithm.all_symbols(),
            self.start_date,
            self.end_date,
        )

        if self.using_intraday:
            self.daily.add_window_padding(self.algorithm.window_padding)
            self.daily.load_all(
                self.algorithm.all_symbols(),
                self.start_date,
                self.end_date,
            )

        self.last_ts = self._current_ts()
        self.end_load_time = time.time()

        self.pbar.start(list(self.historical.global_timestamps), 10)

    def _initialize_indices(self):
        for index in self.algorithm.indices:
            index.initialize(self.historical)
            index.load_all_npz(self.start_date)

    # ==========================================================
    # Reporting
    # ==========================================================

    def report(self):
        self.algorithm.report()

        avg_exposure = (
            self.exposure_time_sum / self.total_time
            if self.total_time > 0
            else 0.0
        )

        Report.print_report(
            self.initial_cash,
            self.portfolio.equity,
            pd.Timestamp(self.start_date),
            self._current_ts(),
            avg_exposure,
            self.start_load_time,
            self.end_load_time,
            self.total_bars,
        )

        if self.should_show_plot:
            Report.show_plots(self.initial_cash)
