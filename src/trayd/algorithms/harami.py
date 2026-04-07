from .algorithm import Algorithm

from trayd.data import OHLCV

from trayd.indicators import SMA, TEST, ROC, ATR
from trayd import Position

from trayd.util import Logger

from trayd.index import SP500, SP100, Top50


class Harami(Algorithm):
    def __init__(self):
        super().__init__("Harami")

        self.portfolio_max_size = 3


    def on_start(self):
        self.test_index = self.add_index(SP500())

        self.sma200 = self.add_indicator(SMA(30))
        self.roc = self.add_indicator(ROC(252))


    def on_tick(self):
        if not self.get_close("SPY") > self.sma200.get("SPY"): return
        if not self.get_close("OEF") > self.sma200.get("OEF"): return
        # if not self.get_close("IWM") > self.sma200.get("IWM"): return

        symbols = self.test_index.get_valid_symbols()
        for symbol in self.roc.rank(symbols):
            curr_open = self.daily.get_open(symbol)
            curr_close = self.daily.get_close(symbol)
            prev_open = self.daily.get_open(symbol, -1)
            prev_close = self.daily.get_close(symbol, -1)

            bearish_prev = prev_open > prev_close
            bullish_curr = curr_close > curr_open
            lower_top = curr_close < prev_open
            higher_bottom = curr_open > prev_close
            inside = lower_top and higher_bottom
            higher_mid = curr_close > (prev_close + prev_open) / 2

            if bearish_prev and bullish_curr and inside:
                self.buy_up_to(symbol)
            elif bearish_prev and bullish_curr and lower_top and not higher_bottom and higher_mid:
                self.buy_up_to(symbol)
            else:
                continue


    # def on_tick(self):
    #     # if not self.get_close("SPY") < self.sma200.get("SPY"): return
    #     # if not self.get_close("OEF") < self.sma200.get("OEF"): return
    #     # if not self.get_close("IWM") < self.sma200.get("IWM"): return

    #     symbols = self.test_index.get_valid_symbols()
    #     for symbol in self.roc.rank(symbols):
    #         curr_open = self.daily.get_open(symbol)
    #         curr_close = self.daily.get_close(symbol)
    #         prev_open = self.daily.get_open(symbol, -1)
    #         prev_close = self.daily.get_close(symbol, -1)

    #         bullish_prev = prev_close > prev_open
    #         bearish_curr = curr_open > curr_close

    #         higher_bottom = curr_close > prev_open
    #         lower_top = curr_open < prev_close
    #         inside = higher_bottom and lower_top

    #         lower_mid = curr_close < (prev_close + prev_open) / 2

    #         if bullish_prev and bearish_curr and inside:
    #             self.short_up_to(symbol)
    #         elif bullish_prev and bearish_curr and higher_bottom and not lower_top and lower_mid:
    #             self.short_up_to(symbol)
    #         else:
    #             continue


    def on_position_opened(self, position: Position):
        self.set_stop_take(position.symbol, position.avg_entry_price, 2, 2)


    def on_position_closed(self, position):
        return
        print(position.symbol, position.entry_time, position.avg_entry_price, position.exit_time, position.avg_fill_price)
            
    

    def end(self):
        pass


