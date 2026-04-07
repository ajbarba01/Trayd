from .algorithm import Algorithm

from trayd.data import OHLCV

from trayd.indicators import SMA, TEST, ROC, ATR, RBC
from trayd import Position

from trayd.util import Logger

from trayd.index import SP500, SP100, Top50

from itertools import combinations


class Arbitrage(Algorithm):
    def __init__(self):
        super().__init__("Arbitrage")

        self.portfolio_max_size = 7


    def on_start(self):
        self.index = self.add_index(SP100())

        self.rbc = self.add_indicator(RBC(90))


    def new_day(self):
        symbols = self.index.get_valid_symbols()

        max = 0.0
        max_pair = None

        for symbol, other in combinations(symbols, 2):
            corr = self.rbc.get_corr(symbol, other)
            if corr > max and set([symbol, other]) != set(["GOOG", "GOOGL"]):
                max = corr
                max_pair = (symbol, other)

        print(self.historical.current_ts, max_pair, max)


    def on_position_opened(self, position: Position):
        self.set_stop_take(position.symbol, position.avg_entry_price, 2, 2)
            
    

    def end(self):
        pass


