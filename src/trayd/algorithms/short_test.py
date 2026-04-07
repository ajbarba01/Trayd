from .algorithm import Algorithm

from trayd.data import OHLCV

from trayd.indicators import SMA, TEST, ROC, ATR
from trayd import Position

from trayd.util import Logger

from trayd.index import SP500, SP100, Top50


class ShortTest(Algorithm):
    def __init__(self):
        super().__init__("Short Test")

        self.portfolio_max_size = 1

        self.started = False
        self.day_count = 0

    def on_start(self):
        self.index = self.add_index(Top50())

    def new_day(self):
        if not self.started:
            self.started = True
            self.short_up_to("SPY")

        else:
            self.day_count += 1

        if self.day_count == 30:
            self.close_position("SPY")

    def end(self):
        pass
