from .algorithm import Algorithm

from trayd.data import OHLCV

from trayd.indicators import SMA, TEST, ROC, ATR, Breakout5
from trayd import Position

from trayd.util import Logger

from trayd.index import SP500, JustSpy, Top50

import numpy as np


class Test(Algorithm):
    def __init__(self):
        super().__init__("Test")

        self.portfolio_max_size = 5


    def on_start(self):
        self.test_index = self.add_index(Top50())

        self.sma200 = self.add_indicator(SMA(200))
        self.roc = self.add_indicator(ROC(252))
        self.atr5 = self.add_indicator(ATR(5))
        self.atr10 = self.add_indicator(ATR(10))


    def on_tick(self):
        if not self.get_close("SPY") > self.sma200.get("SPY"): return
        # if not self.get_close("OEF") > self.sma200.get("OEF"): return
        # if not self.get_close("IWM") > self.sma200.get("IWM"): return

        if self.get_close("SPY") < self.get_close("SPY", -1) * 0.99:
            symbols = self.test_index.get_valid_symbols()
            for symbol in symbols:
                # if self.atr5(symbol) < self.atr10(symbol):
                self.buy_up_to(symbol)


    def on_position_opened(self, position: Position):
        # self.set_stop_loss_ATR(position.symbol, position.avg_entry_price, 2)
        self.set_stop_take(position.symbol, position.avg_entry_price, 2, 2  )
            
    

    def end(self):
        pass


