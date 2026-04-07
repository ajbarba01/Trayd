from .algorithm import Algorithm

from trayd.data import OHLCV

from trayd.indicators import SMA, TEST, ROC, RSI, EMA, ADX

from trayd.util import Logger

from trayd.index import SP500, SP100, Top50

from datetime import time


class Momentum(Algorithm):
    def __init__(self):
        super().__init__("Momentum")

        self.portfolio_max_size = 3


    def on_start(self):
        self.index = self.add_index(SP100())

        self.roc = self.add_indicator(ROC(252))
        self.sma200 = self.add_indicator(SMA(200))


    def new_day(self):
        ranked = self.get_top_roc()
        # print(self.historical.current_ts, len(ranked))
        for symbol in self.portfolio.get_positions():
            if symbol not in ranked:
                self.close_position(symbol)

        for symbol in ranked:
            self.buy_up_to(symbol)



    def on_position_opened(self, position):
        # self.set_stop_take(position.symbol, position.avg_entry_price, 2, 1)
        return
        self.set_stop_loss_ATR(position.symbol, position.avg_entry_price, 3)



    def get_top_roc(self):
        ranked = self.roc.rank(self.index.get_valid_symbols(), max_len=self.portfolio_max_size)
        return ranked
    



