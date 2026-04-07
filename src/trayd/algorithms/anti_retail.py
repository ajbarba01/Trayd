from .algorithm import Algorithm

from trayd.data import OHLCV
from trayd.indicators import SMA, TEST, ROC, ATR, Breakout5, RSI
from trayd.util import Logger
from trayd.index import SP500, SP100, Top50

from trayd import Position

import datetime

import numpy as np


class AntiRetail(Algorithm):
    def __init__(self):
        super().__init__("Anti-Retail")

        self.portfolio_max_size = 10

    def on_start(self):
        self.test_index = self.add_index(SP100())

        self.sma200 = self.add_indicator(SMA(200))
        self.roc = self.add_indicator(ROC(252))
        self.rsi = self.add_indicator(RSI(2))
        self.high_break = self.add_indicator(Breakout5(price=OHLCV.HIGH))
        self.low_break = self.add_indicator(Breakout5(price=OHLCV.LOW))

    def on_tick(self):
        # print(self.daily.current_ts)
        if not self.get_close("SPY") > self.sma200.get("SPY"):
            return
        if not self.get_close("OEF") > self.sma200.get("OEF"):
            return
        # if not self.get_close("IWM") > self.sma200.get("IWM"): return

        time = self.time()

        symbols = self.test_index.get_valid_symbols()
        symbols = self.rsi.filter(symbols, lower_val=15)
        symbols = self.roc.rank(symbols)
        for symbol in symbols:
            if self.low_break.is_five_bar_high(symbol):
                self.buy_up_to(symbol)

        for symbol in self.get_positions():
            if self.high_break.is_five_bar_low(symbol):
                self.close_position(symbol)

    def is_five_bar_high(self, symbol: str):
        return self.high_break.get(symbol) == 1

    def is_five_bar_low(self, symbol: str):
        return self.low_break.get(symbol) == -1

    def on_position_opened(self, position: Position):
        return
        self.set_stop_take(position.symbol, position.avg_entry_price, 1, 2)

    def end(self):
        pass
