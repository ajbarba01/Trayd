from trayd.data import HistoricalData

from trayd.util import Logger
from trayd.util.helpers import downwards_slippage, upwards_slippage, is_intraday

from dataclasses import dataclass

import numpy as np
import pandas as pd

@dataclass
class Position:
    symbol: str
    shares: int
    short: bool
    avg_entry_price: float
    last_known_price: float
    entry_time: pd.Timestamp
    avg_fill_price: float = -1
    exit_time: pd.Timestamp = None


@dataclass
class Order:
    symbol: str
    shares: int
    short: bool
    reference_price: float


class Portfolio:
    def __init__(
        self,
        historical: HistoricalData,
        using_intraday: bool,
        cash: float,
        leverage: float = 1.0,
        margin_interest_rate: float = 0.0625,
        margin_maintenance: float = 0.3,
        max_exposure: float = 1.0
    ):
        self.historical = historical
        self.using_intraday = using_intraday

        self.max_exposure: float = min(max_exposure, leverage)

        self.initial_cash = cash
        self.cash = cash
        self.equity = cash
        self.reserved_value = 0.0

        self.long_value = 0.0
        self.short_value = 0.0
        self.held_value = 0.0
        self.gross_value = 0.0
        self.max_position_value = cash * self.max_exposure
        self.buying_power = self.max_position_value

        self.leverage = max(1.0, leverage)
        self.margin_maintenance = margin_maintenance
        self.margin_interest_rate = margin_interest_rate

        self.positions: dict[str, Position] = {}
        self.pending_orders: dict[str, Order] = {}

        self.total_margin_interest = 0.0

        self.slippage_percent = 0.005
        self.total_slippage = 0.0

        self.stop_losses: dict[str, float] = {}
        self.take_profits: dict[str, float] = {}
        self.trailing_stops: dict[str, tuple] = {}

        self.just_opened: list[Position] = []
        self.just_closed: list[Position] = []

        self.num_trades = 0

        self.last_equity = cash
        self.equitys: list[float] = []
        self.performances: list[float] = []

        self.symbol_profits: dict[str, float] = {}


    def next(self):
        self.just_closed.clear()
        self.just_opened.clear()

        if not self.using_intraday or is_intraday(self.historical.current_ts.time()):
            for order in self.pending_orders.values():
                self._apply_exec(order)

        self.pending_orders.clear()
        self.reserved_value = 0.0

        self._refresh_portfolio_values()

        self._check_stops_takes()
        self._check_delisted()

        self._check_margin_call()


    def new_month(self):
        pass


    def new_day(self):
        self.apply_margin_interest()
        self.performances.append(self.equity / self.last_equity - 1)
        self.equitys.append(self.equity)
        self.last_equity = self.equity


    def get_positions(self):
        return self.positions
    

    def has_position(self, symbol: str) -> bool:
        return symbol in self.positions
    
    
    def get_position(self, symbol: str):
        return self.positions[symbol]
    

    def get_allowance(self):
        return self.buying_power - self.reserved_value


    def _refresh_portfolio_values(self):
        long_value = 0.0
        short_value = 0.0

        for position in self.positions.values():
            symbol = position.symbol
            if self.historical.has_bar(symbol):
                position.last_known_price = self.historical.get_close(symbol)
            
            value = position.shares * position.last_known_price
            if position.short:
                short_value += value
            else:
                long_value += value


        self.long_value = long_value
        self.short_value = short_value
        self.held_value = long_value - short_value
        self.gross_value = long_value + short_value

        self.equity = self.cash + self.held_value
        self.max_position_value = self.equity * self.max_exposure
        self.buying_power = self.max_position_value - self.gross_value


    def _apply_exec(self, order: Order) -> bool:
        if order.short:
            if order.shares > 0:
                return self._exec_buyback(order)
            elif order.shares < 0:
                return self._exec_short(order)
        else:
            if order.shares > 0:
                return self._exec_buy(order)
            elif order.shares < 0:
                return self._exec_sell(order)

        return False


    def _exec_buy(self, order: Order):
        symbol = order.symbol
        if not self.historical.has_bar(symbol): return
        price = upwards_slippage(self.slippage_percent, self.historical.get_open(symbol))

        cost = order.shares * price

        if cost > self.buying_power:
            # Logger.log_error(f"Not enough buying power to buy {symbol}")
            return False
        
        if self.gross_value + cost >= self.max_position_value:
            return False

        self.cash -= cost
        self.buying_power -= cost
        self.total_slippage += (price - order.reference_price) * abs(order.shares)

        existing = self.positions.get(symbol)

        if existing is None:
            pos = Position(
                symbol,
                order.shares,
                False,
                price,
                price,
                self.historical.current_ts
            )
            self.positions[symbol] = pos
            self.just_opened.append(pos)
            return True

        # weighted avg
        total_old = existing.shares * existing.avg_entry_price
        total_add = order.shares * price

        new_shares = existing.shares + order.shares

        existing.avg_entry_price = (
            (total_old + total_add) / new_shares
        )

        existing.shares = new_shares
        existing.last_known_price = price

        return True
    

    def _exec_sell(self, order: Order):
        symbol = order.symbol
        existing = self.positions.get(symbol)

        if existing is None:
            # Logger.log_error(f"Tried to sell {symbol} but no position")
            return False
        
        if not self.historical.has_bar(symbol):
            price = existing.last_known_price
        else:
            price = self.historical.get_open(symbol)
        
        price = downwards_slippage(self.slippage_percent, price)

        if not np.isnan(order.reference_price):
            self.total_slippage += (order.reference_price - price) * abs(order.shares)

        sell_shares = abs(order.shares)

        if sell_shares > existing.shares:
            # Logger.log_error(f"Tried to oversell {symbol}")
            return False

        proceeds = sell_shares * price
        self.cash += proceeds

        remaining = existing.shares - sell_shares

        profit = sell_shares * (price - existing.avg_entry_price)
        if symbol not in self.symbol_profits:
            self.symbol_profits[symbol] = 0
        else:
            self.symbol_profits[symbol] += profit


        if remaining == 0:
            self.num_trades += 1
            existing.avg_fill_price = price
            existing.exit_time = self.historical.current_ts
            self.just_closed.append(existing)
            del self.positions[symbol]
            self.take_profits.pop(symbol, None)
            self.stop_losses.pop(symbol, None)
            self.trailing_stops.pop(symbol, None)
            return True

        existing.shares = remaining
        existing.last_known_price = price

        return True
    

    def _exec_short(self, order: Order):
        symbol = order.symbol
        if not self.historical.has_bar(symbol):
            return False

        price = downwards_slippage(self.slippage_percent, self.historical.get_open(symbol))
        shares = abs(order.shares)
        proceeds = shares * price

        # exposure check
        if self.gross_value + proceeds > self.max_position_value:
            return False

        slippage = (order.reference_price - price) * abs(shares)
        self.total_slippage += slippage
        # print(slippage)
        self.cash += proceeds

        pos = self.positions.get(symbol)

        # NEW SHORT
        if pos is None:
            pos = Position(
                symbol=symbol,
                shares=shares,
                short=True,
                avg_entry_price=price,
                last_known_price=price,
                entry_time=self.historical.current_ts
            )
            self.positions[symbol] = pos
            self.just_opened.append(pos)
            return True

        # ADDING TO EXISTING SHORT
        if not pos.short:
            return False

        total_value = pos.shares * pos.avg_entry_price + shares * price
        pos.shares += shares
        pos.avg_entry_price = total_value / pos.shares
        pos.last_known_price = price

        return True

        
    def _exec_buyback(self, order: Order):
        symbol = order.symbol
        pos = self.positions.get(symbol)
        if pos is None or not pos.short:
            return False

        if not self.historical.has_bar(symbol):
            price = pos.last_known_price
        else:
            price = self.historical.get_open(symbol)

        price = upwards_slippage(self.slippage_percent, price)
        self.total_slippage += (price - order.reference_price) * abs(order.shares)

        shares = abs(order.shares)
        cost = shares * price
        if cost > self.cash:
            return False

        self.cash -= cost
        profit = shares * (pos.avg_entry_price - price)
        self.symbol_profits[symbol] = self.symbol_profits.get(symbol, 0) + profit

        pos.shares -= shares
        pos.last_known_price = price

        if pos.shares == 0:
            self.num_trades += 1
            pos.avg_fill_price = price
            pos.exit_time = self.historical.current_ts
            self.just_closed.append(pos)
            del self.positions[symbol]

        return True


    def place_order(self, symbol: str, shares: int, short=False):
        if symbol in self.pending_orders:
            # Logger.log_error(f"Tried to double place order for {symbol}")
            return False

        if shares == 0:
            return False

        ref_price = self.historical.get_close(symbol)

        self.pending_orders[symbol] = Order(
            symbol,
            shares,
            short,
            ref_price
        )

        if shares > 0 or (short and shares < 0):
            self.reserved_value += abs(shares) * ref_price

        return True
    

    def close_position(self, symbol: str):
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        if pos.short:
            self.place_order(symbol, pos.shares, short=True)
        else:
            self.place_order(symbol, -pos.shares)


    def _check_delisted(self):
        for symbol in self.historical.get_delisted():
            # Logger.log_message(f"Force closed delisted symbol {symbol}: {self.historical.current_ts}")
            self.close_position(symbol)
    

    def _check_stops_takes(self):
        for symbol, (atr, k_val) in self.trailing_stops.items():
            pos = self.positions.get(symbol)
            if pos is None:
                continue

            close = self.historical.get_close(symbol)
            if not pos.short:
                new_stop = close - atr.get(symbol) * k_val
                if new_stop > self.stop_losses.get(symbol, -np.inf):
                    self.stop_losses[symbol] = new_stop
            else:
                new_stop = close + atr.get(symbol) * k_val
                if new_stop < self.stop_losses.get(symbol, np.inf):
                    self.stop_losses[symbol] = new_stop

        for symbol, pos in list(self.positions.items()):
            close = self.historical.get_close(symbol)

            if not pos.short:
                if symbol in self.take_profits and close > self.take_profits[symbol]:
                    self.close_position(symbol)
                elif symbol in self.stop_losses and close < self.stop_losses[symbol]:
                    self.close_position(symbol)
            else:
                if symbol in self.take_profits and close < self.take_profits[symbol]:
                    self.close_position(symbol)
                elif symbol in self.stop_losses and close > self.stop_losses[symbol]:
                    self.close_position(symbol)
    

    def set_take_profit(self, symbol: str, target: float):
        self.take_profits[symbol] = target


    def set_stop_loss(self, symbol: str, limit: float):
        self.stop_losses[symbol] = limit


    def set_trailing_stop(self, symbol: str, atr, k_val: float):
        self.trailing_stops[symbol] = (atr, k_val)
        self.stop_losses[symbol] = self.historical.get_close(symbol) - atr.get(symbol) * k_val


    def _check_margin_call(self):
        return
        if not self.positions:
            return

        equity = self.get_equity()
        required = self.used_margin * self.margin_maintenance

        if equity < required:
            Logger.log_error(
                f"MARGIN CALL! Equity {equity:,.2f} below "
                f"maintenance margin {required:,.2f}"
            )
    
    def apply_margin_interest(self):
        daily_rate = self.margin_interest_rate / 360

        if self.cash < 0:
            interest = -self.cash * daily_rate
            self.cash -= interest
            self.total_margin_interest += interest

        if self.short_value > 0:
            interest = self.short_value * daily_rate
            self.cash -= interest
            self.total_margin_interest += interest