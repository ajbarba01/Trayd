from .algorithm import Algorithm

from trayd.data import OHLCV

from trayd.indicators import SMA, TEST, ROC, ATR, ADX, RSI
from trayd import Position

from trayd.util import Logger

from trayd.index import SP500, SP100, JustSpy, Top50

import numpy as np


class ADXRSI(Algorithm):
    def __init__(self):
        super().__init__("ADX RSI")

        self.portfolio_max_size = 15


    def on_start(self):
        self.test_index = self.add_index(SP100())

        self.sma200 = self.add_indicator(SMA(200))
        self.roc = self.add_indicator(ROC(252))
        self.adx = self.add_indicator(ADX(period=5))
        self.rsi2 = self.add_indicator(RSI(period=2))


    def on_tick(self):
        for symbol in self.get_positions():
            curr_close = self.get_close(symbol)
            prev_high = self.get_high(symbol, -1)
            if curr_close > prev_high:
                self.close_position(symbol)

        if not self.get_close("SPY") > self.sma200.get("SPY"): return
        if not self.get_close("OEF") > self.sma200.get("OEF"): return
        # if not self.get_close("IWM") > self.sma200.get("IWM"): return

        symbols = self.test_index.get_valid_symbols()
        # symbols = [symbol for symbol in self.added_symbols if self.is_valid(symbol)]
        symbols = self.rsi2.filter(symbols, lower_val=85)
        # symbols = self.adx.filter(symbols, lower_val=35, upper_val=50)
        symbols = self.roc.rank(symbols)
        # symbols = [symbol for symbol in symbols if self.get_close(symbol) > self.sma200.get(symbol)]
        for symbol in symbols:
            if self.adx.get(symbol) > self.adx.get(symbol, -1):
                self.buy_up_to(symbol)


    def on_position_opened(self, position: Position):
        return
        self.set_stop_take(position.symbol, position.avg_entry_price, 1, 2)
            
    

    def end(self):
        pass


