from .algorithm import Algorithm

from trayd.data import OHLCV

from trayd.indicators import SMA, TEST, ROC, RSI, EMA, ADX, OvernightGap, Breakout5, ATR, OCMA, BetaMA, RBC, MACDHistogram, MACD

from trayd.util import Logger

from trayd.index import Top50, SP500, SP100, Top25, SP50

from trayd.util.helpers import surround_1

import datetime


class SellOpen(Algorithm):
    def __init__(self):
        super().__init__("Sell Open")

        self.portfolio_max_size = 3

        self.last_trade = {}
        self.last_symbols = []

        self.daily_profits = {i: 0.0 for i in range(7)}

        self.intra_long = set()
        self.intra_short = set()

        self.losses = []


    def on_start(self):
        # Daily
        # self.other = self.add_index(SP100())
        self.index = self.add_index(Top50())

        # what???????
        
        self.roc = self.add_indicator(ROC(504, price=OHLCV.OPEN))
        self.roc_short = self.add_indicator(ROC(21, price=OHLCV.OPEN))
        self.ocma = self.add_indicator(OCMA(500))
        # self.rsi = self.add_indicator(RSI(14))
        self.sma50 = self.add_indicator(SMA(50))
        # buy: 70 > 210, sell: 110 < 230
        self.sma26 = self.add_indicator(SMA(30))
        self.sma15 = self.add_indicator(SMA(7))
        # self.rvol = self.add_indicator(ROC(2, price=OHLCV.VOLUME))
        self.rbc = self.add_indicator(RBC(100))

        self.sma110 = self.add_indicator(SMA(110))
        self.sma230 = self.add_indicator(SMA(230))

        # Intra
        self.atr_intra = self.add_indicator(ATR(14), daily=False)
        self.rsi = self.add_indicator(RSI(2))
        # self.macd = self.add_indicator(MACDHistogram(), daily=False)


    def new_day(self):
        return
        if len(self.index.get_valid_symbols()) == 0:
            print(self.historical.current_ts, self.daily.current_ts)


    def on_position_closed(self, position):
        # self.print_position(position)
        if position.avg_fill_price < position.avg_entry_price:
            self.losses.append(position)
        self.intra_long.discard(position.symbol)
        self.intra_short.discard(position.symbol)
        self.daily_profits[position.exit_time.day_of_week] += position.shares * (position.avg_fill_price - position.avg_entry_price)
        self.last_trade[position.symbol] = (float(position.avg_entry_price), str(position.entry_time), float(position.avg_fill_price), str(position.exit_time), float(position.avg_fill_price) / float(position.avg_entry_price) - 1)
    

    def on_tick(self):
        time = self.time()
        # if time == datetime.time(15, 30):
        #     self.set_trailing_stops()
        # elif time == datetime.time(15, 0):
        #     self.close_all_positions()
        # elif time == datetime.time(15, 45):
        #     self.buy_all()


        # if time == datetime.time(9, 35):
        #     self.short_all()
        # elif time == datetime.time(15, 45):
        #     self.close_all_positions()

        if time == datetime.time(9, 30):
            self.set_trailing_stops()
            self.intra_long.clear()
            self.intra_short.clear()
        elif time == datetime.time(15, 0):
            self.close_all_positions()
        elif time == datetime.time(15, 45):
            self.buy_all()

        # if datetime.time(9, 30) < time < datetime.time(10, 20):
        #     self.tick_intraday()


    def tick_intraday(self):
        if not self.buy_all_intra():
            # return
            self.short_crossover()


    def set_trailing_stops(self):
        # return
        for position in self.get_positions():
            self.set_trailing_stop(position, self.atr_intra, 1.0)


    def buy_all_intra(self):
        # return False
        if self.get_close("SPY") > self.sma26("SPY"): return False
        # if self.get_close("OEF") > self.sma26("OEF"): return False
        # return True

        symbols = self.index.get_valid_symbols()
        symbols = self.rsi.filter(symbols, upper_val=20)
        symbols = self.roc.rank(symbols, descending=True)

        for symbol in symbols:
            self.buy_up_to(symbol)

        return True


    def buy_all(self):
        # return
        # print(self.beta_ma("NVDA"))
        # if not self.sma110("SPY") > self.sma230("SPY"): return
        if self.get_close("SPY") < self.sma50("SPY"): return
        if self.get_close("OEF") < self.sma50("OEF"): return

        symbols = self.index.get_valid_symbols()
        # symbols = self.rsi.filter(symbols, lower_val=30)
        # symbols = self.roc_short.filter(symbols, lower_val=0)
        # symbols = self.roc.rank(symbols)
        
        symbols = self.rank_by_roc(symbols)[:self.portfolio_max_size]
        self.last_symbols.clear()
        self.last_symbols = symbols

        # ranks = {}
        # for symbol in symbols:
        #     rank = 0
        #     for other in symbols:
        #         if symbol != other:
        #             rank += self.rbc.get_corr(symbol, other)
            
        #     ranks[symbol] = 2 / rank

        # self.buy_all_modded(ranks)
         

        # symbols = [symbol for symbol in symbols if symbol in self.other.current_symbols]
        self.buy_all_symbols(symbols)

        # symbols = self.roc.rank(self.index.get_valid_symbols(), descending=False)
        # if symbols:
        #     self.short_up_to(symbols[0])


    def allow_trade(self, symbols: list[str], target: str, max_corr=0.9):
        if not symbols:
            return True

        max_seen = max(
            self.rbc.get_corr(s, target)
            for s in symbols
        )

        return max_seen < max_corr
    

    def on_position_opened(self, position):
        # return
        if position.symbol in self.intra_short:
        # self.set_trailing_stop(position.symbol, self.atr)
            # return
            self.set_static_stop_take(position.symbol, position.avg_entry_price, take_percent=1.5, stop_percent=1)


    def short_crossover(self):
        return
        symbols = self.index.get_valid_symbols()

        # symbols = self.adx.filter(symbols, lower_val=35, upper_val=50)

        for symbol in symbols:

            # macd_momentum = self.macd.get(symbol) - self.macd.get(symbol, offset=-1) > 0.05

            # price = self.historical.get_close(symbol)
            oversold = self.rsi.get(symbol) < 30
            # overbought = self.rsi.get(symbol) > 70
            # rel_close = price / self.last_day.get_close(symbol)
            if self.macd.just_crossed_bearish(symbol) and oversold:
                self.short_up_to(symbol, size=1)
                self.intra_short.add(symbol)


            # if self.macd.just_crossed_bullish(symbol) and overbought:
            #     self.buy_up_to(symbol)



    
    def rank_by_roc(self, symbols: list[str]) -> list[str]:
        symbols = self.rsi.filter(symbols, lower_val=10, offset=0)
        # symbols = self.roc_short.filter(symbols, lower_val=-0.2, offset=1)
        return self.roc.rank(symbols, offset=1)
        ranked = {}
        for symbol in symbols:
            rank = self.roc(symbol) * 1.0 + self.roc_intra(symbol) * 0.0
            ranked[symbol] = rank

        return sorted(ranked, key=ranked.get, reverse=True)
    
    def report(self):
        return
        for position in self.losses:
            loss = position.avg_fill_price / position.avg_entry_price - 1
            if loss < -0.03:
                self.print_position(position)
        

