from .algorithm import Algorithm

from trayd.data import OHLCV

from trayd.indicators import SMA, TEST, ROC, ATR
from trayd import Position

from trayd.util import Logger

from trayd.index import SP500, SP100, Top50


class Scanner(Algorithm):
    def __init__(self):
        super().__init__("Scanner")

        self.portfolio_max_size = 3

    def on_start(self):
        self.index = self.add_index(Top50())

        # self.sma200 = self.add_indicator(SMA(30))
        self.roc = self.add_indicator(ROC(504))
        self.sma50 = self.add_indicator(SMA(50))

    def new_day(self):
        self.print_top()
        # print(self.historical.current_ts, "SPY 50MA:", self.sma50("SPY"), "SPY CLOSE:", self.get_close("SPY"))

    def last_day(self):
        self.print_top()

    def print_top(self):
        print("SPY 50MA:", self.sma50("SPY", offset=1))
        print("SPY CLOSE:", self.get_close("SPY", offset=1))
        if self.get_close("SPY", offset=1) < self.sma50("SPY", offset=1):
            print("SPY BELOW MA")
            return
        # if self.get_close("OEF", offset=1) < self.sma50("OEF", offset=1):
        #     print("OEF BELOW MA")
        #     return

        symbols = self.index.get_valid_symbols()
        # symbols = self.rsi.filter(symbols, lower_val=30)
        # symbols = self.roc_short.filter(symbols, lower_val=0)
        # symbols = self.roc.rank(symbols)

        symbols = self.roc.rank(symbols, offset=1)
        print(
            f"TOP ROC AS OF {self.historical.current_ts.date()}:", symbols[:15]
        )

    def on_position_opened(self, position: Position):
        self.set_stop_take(position.symbol, position.avg_entry_price, 2, 2)

    def end(self):
        pass
