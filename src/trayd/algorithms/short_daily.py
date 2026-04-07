from .algorithm import Algorithm

from trayd.data import OHLCV

from trayd.indicators import (
    SMA,
    TEST,
    ROC,
    RSI,
    EMA,
    ADX,
    OvernightGap,
    Breakout5,
    ATR,
    OCMA,
    BetaMA,
    RBC,
    MACDHistogram,
)

from trayd.util import Logger

from trayd.index import Top50, SP500, SP100, Top25

from trayd.util.helpers import surround_1

import datetime


class ShortDaily(Algorithm):
    def __init__(self):
        super().__init__("Short Daily")

        self.portfolio_max_size = 3

        self.to_short_today = set()

    def on_start(self):
        self.index = self.add_index(SP100())
        self.roc = self.add_indicator(ROC(100))
        self.sma230 = self.add_indicator(SMA(230))
        self.sma110 = self.add_indicator(SMA(110))
        self.sma200 = self.add_indicator(SMA(210))
        self.sma26 = self.add_indicator(SMA(70))

        self.rsi = self.add_indicator(RSI(2))

    def on_tick(self):
        self.close_some()
        self.short_all()
        # self.short_crossover()
        return

        symbols = self.index.get_valid_symbols()
        # symbols = self.rsi.filter(symbols, lower_val=15)
        # symbols = self.roc.rank(symbols, descending=False)
        for symbol in symbols:
            if self.high_break.is_five_bar_high(symbol):
                self.to_short_today.add(symbol)

        if not self.get_close("SPY") > self.sma200.get("SPY"):
            return
        if not self.get_close("OEF") > self.sma200.get("OEF"):
            return
        # if not self.get_close("IWM") > self.sma200.get("IWM"): return

        self.to_short_today = set(
            [
                symbol
                for symbol in self.to_short_today
                if not self.low_break.is_five_bar_low(symbol)
            ]
        )

    def on_position_opened(self, position):
        return
        # self.set_trailing_stop(position.symbol, self.atr)
        self.set_static_stop_take(
            position.symbol, position.avg_fill_price, 1.5, 1
        )

    def close_some(self):
        # return
        if self.sma26("SPY") > self.sma200("SPY"):
            self.close_all_positions()

        return

        symbol_set = set(self.get_candidates())

        for position in self.get_positions():
            if position not in symbol_set:
                self.close_position(position)

    def short_all(self):
        if self.sma110("SPY") < self.sma230("SPY"):
            self.short_up_to("OEF")

    def get_candidates(self) -> list[str]:
        symbols = self.index.get_valid_symbols()
        symbols = self.rsi.filter(symbols, upper_val=90)
        symbols = self.roc.filter(symbols, upper_val=0)
        return self.roc.rank(symbols, descending=False)[
            : self.portfolio_max_size
        ]

    def short_crossover(self):
        symbols = self.index.get_valid_symbols()

        for symbol in symbols:

            # macd_momentum = self.macd.get(symbol) - self.macd.get(symbol, offset=-1) > 0.05

            price = self.historical.get_close(symbol)
            oversold = self.rsi.get(symbol) > 30
            # rel_close = price / self.last_day.get_close(symbol)
            if self.macd.just_crossed_bearish(symbol) and not oversold:
                self.short_up_to(symbol)
