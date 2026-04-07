from .algorithm import Algorithm

from trayd.indicators import *
from trayd import Position
from trayd.index import *


class FailedBreakoutShort(Algorithm):
    def __init__(self):
        super().__init__("FailedBreakoutShort")

        self.portfolio_max_size = 5
        self.lookback = 252      # breakout window
        self.max_age = 3        # days since breakout

        self.breakout_days = {}


    def on_start(self):
        self.index = self.add_index(Top50())

        # Trend / regime
        self.sma5 = self.add_indicator(SMA(5))
        self.sma20 = self.add_indicator(SMA(5))
        self.sma200 = self.add_indicator(SMA(200))

        # Exhaustion
        self.rsi = self.add_indicator(RSI(14))

        # Rank strong names
        self.roc = self.add_indicator(ROC(126))
        self.ath = self.add_indicator(ATH(self.lookback))


    def on_tick(self):
        for symbol in self.get_positions():
            if self.rsi(symbol) < 50:
                self.close_position(symbol)

        for symbol in self.breakout_days:
            self.breakout_days[symbol] -= 1

        self.breakout_days = {symbol: days_ago for symbol, days_ago in self.breakout_days.items() if days_ago > -3}

        # Risk-off regime only
        if self.get_close("SPY") > self.sma5.get("SPY"):
            return

        symbols = self.index.get_valid_symbols()

        for symbol in symbols:
            if self.get_close(symbol) > self.ath.get(symbol, -1):
                self.breakout_days[symbol] = 0


        for symbol in self.roc.rank(symbols):
            price = self.get_close(symbol)
            rsi = self.rsi.get(symbol)
            sma200 = self.sma200.get(symbol)

            if price > self.ath.get(symbol, -1) and self.rsi.get(symbol) > 70:
                self.short_up_to(symbol)

            continue

            # Only mean-reversion shorts
            if price < sma200:
                continue

            # Highest close over lookback (excluding today)
            prior_high = self.ath.get(symbol, -1)
            # if symbol == "MSFT":
            #     print(prior_high)

            # Detect recent breakout
            breakout_day = self.breakout_days.get(symbol)

            if breakout_day is None:
                continue

            # Failure condition: close back below breakout level
            if price >= prior_high:
                continue

            # Optional exhaustion filter
            # if rsi < 65:
            #     continue

            self.short_up_to(symbol)


    def on_position_opened(self, position: Position):
        self.set_trailing_stop(position.symbol, k_val=2)
        self.set_take_profit(position.symbol, position.avg_entry_price * (0.98))
        return
        
        self.set_static_stop_take(position.symbol, position.avg_entry_price, 2.0, 2.0)


    def on_position_closed(self, position: Position):
        self.print_position(position)


    def end(self):
        pass
