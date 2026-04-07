from .algorithm import Algorithm

from trayd.data import OHLCV
from trayd.indicators import SMA, TEST, ROC, RSI, EMA, ADX, OvernightGap, Breakout5, ATR, OCMA, BetaMA, RBC, MACDHistogram
from trayd.util import Logger
from trayd.index import Top50, SP500, SP100, Top25

from trayd.util.helpers import surround_1

import datetime


class IntraShort(Algorithm):
    def __init__(self):
        super().__init__("Intra Short")

        self.portfolio_max_size = 1

        self.to_short_today = set()


    def on_start(self):
        self.index = self.add_index(Top50())
        self.roc = self.add_indicator(ROC(504))
        self.sma200 = self.add_indicator(SMA(200))
        
        self.rsi = self.add_indicator(RSI(14), daily=False)
        self.macd = self.add_indicator(MACDHistogram(), daily=False)
        self.atr = self.add_indicator(ATR(14), daily=False)
        self.adx = self.add_indicator(ADX(5), daily=False)

        self.set_default_atr(self.atr)


    def new_day(self):
        return

        symbols = self.index.get_valid_symbols()
        # symbols = self.rsi.filter(symbols, lower_val=15)
        # symbols = self.roc.rank(symbols, descending=False)
        for symbol in symbols:
            if self.high_break.is_five_bar_high(symbol):
                self.to_short_today.add(symbol)

        if not self.get_close("SPY") > self.sma200.get("SPY"): return
        if not self.get_close("OEF") > self.sma200.get("OEF"): return
        # if not self.get_close("IWM") > self.sma200.get("IWM"): return

        self.to_short_today = set([symbol for symbol in self.to_short_today if not self.low_break.is_five_bar_low(symbol)])


    def on_tick(self):
        time = self.time()
        if time == datetime.time(15, 45):
            self.close_all_positions()
        # elif time == datetime.time(15, 30) and self.is_valid("MSFT"):
        #     print(self.historical.current_ts, self.rsi.get("MSFT"))

        if datetime.time(9, 30) < time < datetime.time(10, 20):
            self.short_crossover()


    def on_position_opened(self, position):
        # self.set_trailing_stop(position.symbol, self.atr)
        self.set_static_stop_take(position.symbol, position.avg_fill_price, 1.5, 1)


    def short_crossover(self):
        symbols = self.index.get_valid_symbols()

        # symbols = self.adx.filter(symbols, lower_val=35, upper_val=50)

        for symbol in symbols:

            # macd_momentum = self.macd.get(symbol) - self.macd.get(symbol, offset=-1) > 0.05

            price = self.historical.get_close(symbol)
            oversold = self.rsi.get(symbol) < 30
            overbought = self.rsi.get(symbol) > 70
            # rel_close = price / self.last_day.get_close(symbol)
            if self.macd.just_crossed_bearish(symbol) and oversold:
                self.short_up_to(symbol)


            # if self.macd.just_crossed_bullish(symbol) and overbought:
            #     self.buy_up_to(symbol)

