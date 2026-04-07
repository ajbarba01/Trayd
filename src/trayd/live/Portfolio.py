from alpaca.trading.models import TradeAccount, Order, TradeUpdate
from alpaca.trading.enums import OrderSide, OrderStatus, TradeEvent, OrderType

from live.Alpaca import Alpaca
from live.Logger import Logger
from live.LiveData import LiveData
from live.models import LocalPosition

from live.helpers import format_USD

import threading
import queue
import time


class Portfolio:
    def __init__(self, alpaca: Alpaca, live_data: LiveData):
        self.alpaca = alpaca
        self.live_data = live_data

        self.order_lock = threading.Lock()

        self.account: TradeAccount | None = None
        self.cash: float = 0.0
        self.allowance: float = 0.0
        self.portfolio_value: float = 0.0
        self.holdings_value: float = 0.0
        self.buying_power: float = 0.0

        self.positions: dict[str, LocalPosition] = {}
        self.orders: dict[str, Order] = {}

        self.open_buys: set[str] = set()
        self.open_sells: set[str] = set()

        self.seen_executions: set[str] = set()

        self.company_ranks = {}

        self.market_buy_reqs = {}
        self.market_sell_reqs = {}

        self.total_slippage: float = 0.0
        self.profit: float = 0.0

        self.order_book = {}
        self.cancel_after = 3.0
        
        self.margin_usage = 0.0


    def set_margin_usage(self, margin_usage: float):
        self.margin_usage = max(0.0, min(1.0, margin_usage))


    def new_day(self):
        self.profit = 0.0
        self.total_slippage = 0.0


    def max_deployable_capital(self) -> float:
        return self.cash + self.margin_usage * (self.buying_power - self.cash)


    # -------------------------
    # Account refresh
    # -------------------------
    def refresh_account_values(self):
        account = self.alpaca.get_account_info()
        if account:
            self.buying_power = float(account.buying_power)
            self.portfolio_value = float(account.portfolio_value)
            self.holdings_value = self.portfolio_value - float(account.cash)


    # -------------------------
    # Trade update handling
    # -------------------------
    def handle_trade_updates(self, trade_queue: queue.Queue):
        while True:
            try:
                trade: TradeUpdate = trade_queue.get_nowait()
            except queue.Empty:
                break
            
            if trade.order.id not in self.orders:
                # Still allow executions & terminal cleanup
                if trade.event in (TradeEvent.PARTIAL_FILL, TradeEvent.FILL):
                    self.apply_execution(trade)

                if trade.event in (
                    TradeEvent.FILL,
                    TradeEvent.CANCELED,
                    TradeEvent.REJECTED,
                    TradeEvent.EXPIRED,
                ):
                    self.remove_order(trade.order.id)

                continue

            if trade.event in (TradeEvent.PARTIAL_FILL, TradeEvent.FILL):
                self.apply_execution(trade)

            if trade.event == TradeEvent.ACCEPTED:
                self.accept_order(trade.order)

            if trade.event in (
                TradeEvent.FILL,
                TradeEvent.CANCELED,
                TradeEvent.REJECTED,
                TradeEvent.EXPIRED,
            ):
                self.remove_order(trade.order.id)

        self.calculate_allowance()
        self.cancel_old_market()


    def cancel_old_market(self):

        def _cancel_old_market():
            now = time.time()
            with self.order_lock:
                for order_id, timestamp in self.order_book.items():
                    if now - timestamp > self.cancel_after:
                        self.alpaca.cancel_order(order_id)
        
        thread = threading.Thread(target=_cancel_old_market, daemon=True)
        thread.start()


    def calculate_allowance(self):
        allowed = self.max_deployable_capital()

        committed = 0.0
        for order in self.orders.values():
            if order.side == OrderSide.BUY:
                remaining = float(order.qty) - float(order.filled_qty)

                if order.order_type == OrderType.LIMIT:
                    committed += remaining * float(order.limit_price)
                elif order.order_type == OrderType.MARKET:
                    committed += remaining * self.market_buy_reqs.get(order.symbol, 0)

        self.allowance = max(0.0, allowed - committed)


    # -------------------------
    # Execution application
    # -------------------------
    def apply_execution(self, trade: TradeUpdate):
        exec_id = trade.execution_id
        if exec_id in self.seen_executions:
            return

        self.seen_executions.add(exec_id)

        symbol = trade.order.symbol
        qty = float(trade.qty)
        price = float(trade.price)
        side = trade.order.side

        position = self.ensure_position(symbol)

        if side == OrderSide.BUY:
            if trade.order.order_type == OrderType.MARKET and symbol in self.market_buy_reqs:
                # calculate slippage
                self.total_slippage += qty * (price - self.market_buy_reqs[symbol])
            new_qty = self.update_avg_entry(position, qty, price)
            self.cash -= qty * price
            Logger.log_event(f"BOUGHT {int(qty)} {symbol}: {format_USD(qty * price)}")

        elif side == OrderSide.SELL:
            if trade.order.order_type == OrderType.MARKET and symbol in self.market_sell_reqs:
                # calculate slippage
                self.total_slippage += qty * (self.market_sell_reqs[symbol] - price)
            new_qty = float(position.qty) - qty
            self.cash += qty * price
            profit = qty * (price - float(position.avg_entry_price))
            self.profit += profit
            Logger.log_event(f"SOLD {int(qty)} {symbol}: {format_USD(qty * price)}, profit {format_USD(profit)}")

        position.qty = new_qty

        # Cleanup empty positions
        if position.qty == 0:
            position.avg_entry_price = 0.0
            self.positions.pop(symbol)
        elif position.qty < 0:
            raise RuntimeError(f"Oversold position: {symbol}")


    # -------------------------
    # Order lifecycle
    # -------------------------
    def accept_order(self, order: Order):
        if order.id in self.orders:
            self.orders[order.id].status = OrderStatus.ACCEPTED


    def remove_order(self, order_id: str):
        order = self.orders.pop(order_id, None)
        if not order:
            Logger.log_message("ORDER REMOVAL NOT IN ORDER (BAD!!!)")
            return

        symbol = order.symbol

        if order.side == OrderSide.BUY:
            self.open_buys.discard(symbol)
            self.market_buy_reqs.pop(symbol, None)

        elif order.side == OrderSide.SELL:
            self.open_sells.discard(symbol)
            self.market_sell_reqs.pop(symbol, None)

        with self.order_lock:
            self.order_book.pop(order_id, None)


    def sell_all(self, symbol: str, price_per: float, market=False):
        if symbol in self.positions:
            position = self.get_position(symbol)
            qty = float(position.qty)
            self.place_sell(symbol, price_per, qty, market=market)
        else:
            Logger.log_error(f"Tried to sell non-existent {symbol}")

    
    def buy_up_to(self, symbol: str, price_per: float, wanted_shares: int, market=False):
        Logger.log_message(f"BUYING {symbol}")
        if symbol in self.positions:
            position = self.get_position(symbol)
            wanted_shares = wanted_shares - int(position.qty)

        # Logger.log_message(f"{symbol}: {position.qty * price_per}")

        if wanted_shares <= 0:
            return
        
        if symbol in self.open_buys:
            Logger.log_error(f"Doubled buy order {symbol}")
            return
        
        worst_price = price_per
        if market:
            worst_price = self.live_data.get_high(symbol)

        # Don't buy if not enough allowance
        if worst_price * wanted_shares > self.allowance: return

        self.place_buy(symbol, price_per, wanted_shares, market=market)


    # -------------------------
    # Order placement
    # -------------------------
    def place_buy(self, symbol: str, price_per: float, shares: int, market: bool):
        if shares <= 0:
            Logger.log_message(f"Cannot place BUY order for {shares} shares: {symbol}")
            return
        
        if price_per <= 0:
            Logger.log_message(f"Cannot place BUY order for ${format_USD(price_per)}")
            return
        
        if symbol in self.open_sells:
            Logger.log_error(f"Tried to BUY just placed SELL {symbol}")
            return

        total_cost = price_per * shares
        if total_cost > self.allowance:
            Logger.log_message(f"Cannot place BUY order for {symbol}: insufficient allowance")
            return

        if market:
            order = self.alpaca.buy_market(symbol, shares)
        else:
            order = self.alpaca.buy_limit(symbol, price_per, shares)
        if order:
            self.orders[order.id] = order
            if market: 
                self.order_book[order.id] = time.time()
                self.market_buy_reqs[symbol] = price_per
        else:
            Logger.log_error("Buy order failed from Alpaca")

        self.open_buys.add(symbol)
        self.allowance -= total_cost


    def place_sell(self, symbol: str, price_per: float, shares: int, market: bool):
        if shares <= 0 :
            Logger.log_message(f"Cannot place SELL order for {shares} shares")
            return
        
        if price_per <= 0:
            Logger.log_message(f"Cannot place SELL order for ${format_USD(price_per)}")
            return
        
        if symbol in self.open_buys:
            Logger.log_error(f"Tried to SELL just placed BUY {symbol}")
            return
        
        if symbol not in self.positions:
            Logger.log_error(f"Tried to SELL non-existent {symbol}")
            return

        position = self.positions[symbol]
        if shares > position.qty:
            Logger.log_error(f"Cannot place SELL order for {symbol}: not enough shares")
            return

        if market:
            order = self.alpaca.sell_market(symbol, shares)
        else:
            order = self.alpaca.sell_limit(symbol, price_per, shares)
        if order:
            self.orders[order.id] = order
            if market: 
                self.order_book[order.id] = time.time()
                self.market_sell_reqs[symbol] = price_per
        else:
            Logger.log_error("Sell order failed from Alpaca")

        self.open_sells.add(symbol)


    # -------------------------
    # Initialization
    # -------------------------
    def reconnect(self):
        self.account = self.alpaca.get_account_info()
        self.cash = float(self.account.cash)
        self.portfolio_value = float(self.account.portfolio_value)
        self.holdings_value = self.portfolio_value - self.cash

        # Load positions from Alpaca
        self.positions.clear()
        for p in self.alpaca.get_positions() or []:
            self.positions[p.symbol] = LocalPosition(
                symbol=p.symbol,
                qty=float(p.qty),
                avg_entry_price=float(p.avg_entry_price),
            )

        # Load open orders
        self.orders.clear()
        total_pending_buy = 0.0

        for order in self.alpaca.get_all_orders() or []:
            if not order.limit_price:
                Logger.log_message("Found non-limit order")
                continue

            self.orders[order.id] = order

            if order.side == OrderSide.BUY:
                total_pending_buy += float(order.qty) * float(order.limit_price)

        self.allowance = self.cash - total_pending_buy


    # -------------------------
    # Helpers
    # -------------------------

    def update_avg_entry(self, position: LocalPosition, qty: float, price: float):
        old_qty = float(position.qty)
        new_qty = old_qty + qty

        if old_qty == 0:
            position.avg_entry_price = price
        else:
            position.avg_entry_price = (
                (old_qty * position.avg_entry_price) +
                (qty * price)
            ) / new_qty

        return new_qty

    def ensure_position(self, symbol: str) -> LocalPosition:
        if symbol not in self.positions:
            self.positions[symbol] = LocalPosition(symbol=symbol)
        return self.positions[symbol]


    def has_open_buy(self, symbol: str) -> bool:
        return symbol in self.open_buys


    def has_open_sell(self, symbol: str) -> bool:
        return symbol in self.open_sells


    def has_position(self, symbol: str) -> bool:
        return symbol in self.positions


    def get_position(self, symbol: str) -> LocalPosition:
        return self.positions[symbol]
    

    def has_positions(self) -> bool:
        return len(self.positions) > 0
    

    def get_positions(self) -> dict:
        return self.positions
    

    def get_valid_positions(self, live_data: LiveData):
        return {symbol: position for symbol, position in self.positions.items() 
                if live_data.has_quote(symbol)}
    
    def get_valid_quotes(self, live_data: LiveData):
        return [symbol for symbol in live_data.get_quotes()]
    

    def close_all_positions(self):
        self.alpaca.close_all_positions()


    # -------------------------
    # Debug
    # -------------------------
    def debug_output(self):
        Logger.log_message(f"ACCOUNT STATUS: {self.account.status}")
        Logger.log_message(f"CASH VALUE: {format_USD(self.cash)}")
        Logger.log_message(f"PORTFOLIO VALUE: {format_USD(self.portfolio_value)}")
        Logger.log_message(f"HOLDINGS VALUE: {format_USD(self.holdings_value)}")
        Logger.log_message(
            f"POSITIONS: { {s: p.qty for s, p in self.positions.items()} }"
        )
        Logger.log_message(
            f"ORDERS: { {o.id: float(o.qty) for o in self.orders.values()} }"
        )
