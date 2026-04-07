from trayd.data import HistoricalData
from trayd.indicators import Indicator, ATR
from trayd import Portfolio, Position
from trayd.index import Index

from trayd.util import Logger
from trayd.util.helpers import SMA, EMA

from trayd import Report

from datetime import time
from typing import TypeVar

import pandas as pd
import numpy as np

T = TypeVar("T", bound=Indicator)


class Algorithm:
    def __init__(self, name: str):
        self.name = name
        self.historical = None
        self.daily = None
        self.portfolio = None
        self.window_padding = 5

        self.portfolio_max_size = 7.0
        self.indices: list[Index] = []

        self.added_symbols: list[str] = ["SPY", "OEF", "IWM", "QQQ", "VIX"]

    def initialize(
        self,
        historical: HistoricalData,
        daily: HistoricalData,
        portfolio: Portfolio,
    ):
        self.historical = historical
        self.daily = daily
        self.portfolio = portfolio

    def start(self):
        Report.add_equity_curve(self)

        if self.daily:
            self.default_atr = self.daily.add_indicator(ATR(14))

        self.on_start()

    def on_start(self):
        pass

    def tick(self):
        # THIS IS BAD
        if (
            self.historical.current_ts.normalize()
            != self.daily.current_ts.normalize()
        ):
            return

        for position in self.portfolio.just_opened:
            self.on_position_opened(position)

        for symbol in self.portfolio.just_closed:
            self.on_position_closed(symbol)

        self.on_tick()

    def on_position_opened(self, position: Position):
        pass

    def on_position_closed(self, position: Position):
        pass

    def on_tick(self):
        pass

    def new_day(self):
        pass

    def last_day(self):
        pass

    def new_month(self):
        pass

    def is_valid(self, symbol: str) -> bool:
        return self.historical.is_valid(symbol)

    def add_indicator(self, ind: T, daily=True) -> T:
        if daily:
            return self.daily.add_indicator(ind)
        else:
            return self.historical.add_indicator(ind)

    def add_index(self, index: Index):
        self.indices.append(index)
        return index

    def add_symbol(self, symbol: str):
        self.added_symbols.append(symbol)

    def all_symbols(self) -> dict[str, pd.Timestamp]:
        all = {symbol: None for symbol in self.added_symbols}

        for index in self.indices:
            all.update(index.symbol_starts)

        return all

    def day_of_week(self) -> int:
        return self.historical.current_ts.day_of_week

    def month(self) -> int:
        return self.historical.current_ts.month

    def time(self) -> time:
        return self.historical.current_ts.time()

    def buy_up_to(
        self,
        symbol: str,
        shares: float = None,
        mod: float = 1.0,
        size: int = None,
    ):
        if not size:
            size = self.portfolio_max_size
        if not shares:
            shares = self.closest_share_amount(symbol, mod=mod)
        if shares:
            self.buy(symbol, shares)

    def buy_all_symbols(self, symbols: list[str]):
        for symbol in symbols:
            self.buy_up_to(symbol)

    def buy_all_modded(self, symbols: dict[str, float]):
        for symbol, mod in symbols.items():
            self.buy_up_to(symbol, mod=mod)

    def buy(self, symbol: str, shares: float):
        self.portfolio.place_order(symbol, shares)

    def short_up_to(
        self,
        symbol: str,
        shares: float = None,
        mod: float = 1.0,
        size: float = None,
    ):
        if not size:
            size = self.portfolio_max_size
        if not shares:
            shares = -self.closest_share_amount(symbol, mod=mod, max_size=size)
        if shares:
            self.short(symbol, shares)

    def short_all_symbols(self, symbols: list[str]):
        for symbol in symbols:
            self.short_up_to(symbol)

    def short_all_modded(self, symbols: dict[str, float]):
        for symbol, mod in symbols.items():
            self.short_up_to(symbol, mod=mod)

    def short(self, symbol: str, shares: float):
        self.portfolio.place_order(symbol, -abs(shares), short=True)

    def close_position(self, symbol: str):
        self.portfolio.close_position(symbol)

    def close_all_positions(self):
        for position in self.portfolio.get_positions():
            self.portfolio.close_position(position)

    def close_all_symbols(self, symbols: list[str] = None):
        for symbol in symbols:
            if self.portfolio.has_position(symbol):
                self.portfolio.close_position(symbol)

    def company_per(self, portfolio_max_size: float = None) -> float:
        if not portfolio_max_size:
            portfolio_max_size = self.portfolio_max_size

        return self.portfolio.max_position_value / portfolio_max_size

    def closest_share_amount(
        self,
        symbol: str,
        max_price: float = None,
        max_size: float = None,
        mod: float = 1.0,
    ):
        if not max_price:
            max_price = self.company_per(max_size)

        max_price *= mod
        price = self.historical.get_close(symbol)
        if np.isnan(price):
            return 0

        max_by_allocation = max_price // price
        max_by_buying_power = self.portfolio.get_allowance() // price

        return int(min(max_by_buying_power, max_by_allocation))

    def set_default_atr(self, atr: ATR):
        self.default_atr = atr

    def set_take_profit(self, symbol: str, target: float):
        self.portfolio.set_take_profit(symbol, target)

    def set_take_profit_ATR(self, symbol: str, price: float, k_val: float):
        target = price + k_val * self.default_atr.get(symbol)
        self.portfolio.set_take_profit(symbol, target)

    def set_stop_loss(self, symbol: str, limit: float):
        self.portfolio.set_stop_loss(symbol, limit)

    def set_stop_loss_ATR(self, symbol: str, price: float, k_val: float):
        limit = price - k_val * self.default_atr.get(symbol)
        self.portfolio.set_stop_loss(symbol, limit)

    def set_stop_take(
        self, symbol: str, price: float, take_k: float, stop_k: float
    ):
        self.set_take_profit_ATR(symbol, price, take_k)
        self.set_stop_loss_ATR(symbol, price, stop_k)

    def set_static_stop_take(
        self,
        symbol: str,
        price: float,
        take_percent: float = None,
        stop_percent: float = None,
    ):
        if take_percent:
            self.portfolio.set_take_profit(
                symbol, price * 1 + take_percent / 100
            )

        if stop_percent:
            self.portfolio.set_take_profit(
                symbol, price * 1 - stop_percent / 100
            )

    def set_trailing_stop(
        self, symbol: str, atr: Indicator = None, k_val: float = 1
    ):
        if not atr:
            atr = self.default_atr
        self.portfolio.set_trailing_stop(symbol, atr, k_val)

    def end(self):
        pass

    def report(self):
        Report.set_performance(
            self.name, SMA(EMA(self.portfolio.performances, 30), 60)
        )
        self.on_report()

    def on_report(self):
        pass

    def get_open(self, symbol: str, offset: int = 0, daily=False) -> float:
        if daily:
            return self.daily.get_open(symbol, offset)
        else:
            return self.historical.get_open(symbol, offset)

    def get_high(self, symbol: str, offset: int = 0, daily=False) -> float:
        if daily:
            return self.daily.get_high(symbol, offset)
        else:
            return self.historical.get_high(symbol, offset)

    def get_low(self, symbol: str, offset: int = 0, daily=False) -> float:
        if daily:
            return self.daily.get_low(symbol, offset)
        else:
            return self.historical.get_low(symbol, offset)

    def get_close(self, symbol: str, offset: int = 0, daily=False) -> float:
        if daily:
            return self.daily.get_close(symbol, offset)
        else:
            return self.historical.get_close(symbol, offset)

    def get_volume(self, symbol: str, offset: int = 0, daily=False) -> float:
        if daily:
            return self.daily.get_volume(symbol, offset)
        else:
            return self.historical.get_volume(symbol, offset)

    def get_VWAP(self, symbol: str, offset: int = 0) -> float:
        return self.historical.get_VWAP(symbol, offset)

    def get_positions(self):
        return self.portfolio.get_positions()

    def print_position(self, position: Position):
        print(
            position.symbol,
            position.entry_time,
            position.avg_entry_price,
            position.exit_time,
            position.avg_fill_price,
        )
