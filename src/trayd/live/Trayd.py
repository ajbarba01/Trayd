from alpaca.data.models import Quote
from alpaca.trading.models import TradeUpdate, Position, TradeAccount, Order
from alpaca.trading.enums import OrderSide, OrderStatus

from live.Alpaca import Alpaca
from live.Terminal import Terminal
from live.LiveData import LiveData
# from TraydUX import TraydUX
from live.Portfolio import Portfolio
from live.Config import Config
from live.Logger import Logger
from live.Algorithm import Algorithm
from live.NonVolatile import NonVolatile, Variable

from live.Index import Index


from zoneinfo import ZoneInfo
from datetime import datetime

import datetime as dt
import platform
import pytz
import queue
import time
import threading

# Detect if running on ARM (Raspberry Pi)
IS_ARM = platform.machine().startswith("arm") or platform.machine().startswith("aarch")

# Only import GUI if not on ARM
if not IS_ARM:
    from TraydUX import TraydUX
else:
    TraydUX = None  # placeholder for type safety



class Trayd:
    def __init__(self):
        self.et = ZoneInfo("America/New_York")

        self.alpaca = Alpaca()
        self.terminal = Terminal()
        self.index = Index()

        self.live_data = LiveData(self.index, self.alpaca, self.et)

        self.portfolio = Portfolio(self.alpaca, self.live_data)

        if TraydUX is not None:
            self.trayd_ux = TraydUX(self.portfolio)
            self.has_gui = True
            self.using_terminal = True
        else:
            self.trayd_ux = None
            self.has_gui = False
            self.using_terminal = False
            Config.can_run = True

        self.algorithm: Algorithm = MACD(self.index, self.portfolio, self.live_data)

        # Step counters
        self.last_tick = 0.0
        self.last_extended_tick = 0.0
        self.last_portfolio_update = 0.0
        self.last_validation = 0.0
        self.last_secondary_validation = 0.0
        self.last_render = 0.0
        self.last_extended_check = 0.0

        self.cancelled = False
        self.algorithm_enabled = False
        self.using_data_stream = False

        # Program settings
        self.can_output = False
        self.running = True

        self.connected = True
        self.extended_hours = False

        self.portfolio_update_event = threading.Event()
        self.portfolio_update_lock = threading.Lock()
        self.portfolio_thread_running = False

        self.cancel_update_event = threading.Event()
        self.cancel_update_lock = threading.Lock()
        self.cancel_thread_running = False

        self.started = False

        self.current_day = datetime.now(self.et).date()
        

    def run(self):
        self.initialize()

        try:
            self.main_loop()

        except KeyboardInterrupt:
            self.print("KEYBOARD INTERRUPT")

        self.on_exit()


    def main_loop(self):
        while self.running:
            self.step()
            time.sleep(Config.main_loop_rate)


    def step(self):
        if self.using_terminal:
            self.handle_user_input()

        self.check_extended_hours()
        self.check_connection()

        self.validate()
        self.secondary_validation()

        self.cancel_deferred()
        
        self.algorithm_tick()
        self.update_portfolio()

        if self.has_gui:
            self.trayd_ux.update()
            if self.trayd_ux.wants_to_exit:
                self.running = False


    def check_extended_hours(self):
        if time.time() - Config.extended_check_rate > self.last_extended_check:
            self.last_extended_check = time.time()
        else: return
                
        now_dt = dt.datetime.now(self.et)

        market_open = dt.time(9, 30)
        market_close = dt.time(16, 0)

        is_weekend = now_dt.weekday() >= 5
        is_regular_time = market_open <= now_dt.time() < market_close

        extended = is_weekend or not is_regular_time

        if not self.extended_hours and extended:
            self.enter_extended_hours()

        if self.extended_hours and not extended:
            self.enter_normal_hours()


    def enter_extended_hours(self):
        self.extended_hours = True
        self.live_data.set_extended_hours()
        Logger.log_message("Trading on extended hours")
        
        if self.has_gui:
            self.trayd_ux.set_extended(True)

    
    def enter_normal_hours(self):
        if not self.started: self.started = True
        else:
            self.alpaca.close_all_positions()

        self.extended_hours = False
        self.live_data.set_normal_hours()
        Logger.log_message("Trading on regular hours")
        if self.has_gui:
            self.trayd_ux.set_extended(False)


    def check_connection(self):
        if self.alpaca.is_connected() and not self.connected:
            self.reconnect()
        elif not self.alpaca.is_connected() and self.connected:
            self.disconnect()


    def reconnect(self):
        self.connected = True
        self.portfolio.reconnect()
        if self.has_gui:
            self.trayd_ux.set_connected(True)
        self.live_data.initialize_indicators()


    def disconnect(self):
        self.connected = False
        if self.has_gui:
            self.trayd_ux.set_connected(False)


    def update_portfolio(self):
        if time.time() - Config.portfolio_refresh_rate <= self.last_portfolio_update:
            return

        if not self.alpaca.is_connected():
            return

        # Don't start another update if one is running
        if self.portfolio_thread_running:
            return

        self.last_portfolio_update = time.time()
        self.portfolio_thread_running = True
        self.portfolio_update_event.clear()

        threading.Thread(
            target=self._portfolio_update_worker,
            daemon=True
        ).start()


    def _portfolio_update_worker(self):
        try:
            with self.portfolio_update_lock:
                self.portfolio.refresh_account_values()
        except Exception as e:
            Logger.log_error(f"Portfolio update failed: {e}")
        finally:
            self.portfolio_thread_running = False
            self.portfolio_update_event.set()


    def cancel_deferred(self):
        if self.cancelled: return
        if not self.algorithm.should_cancel: return
        
        should_cancel = False
        now = time.time()
        
        if self.extended_hours and now - self.algorithm.extended_cancel_defer > self.last_extended_tick:
            should_cancel = True

        elif now - self.algorithm.cancel_defer > self.last_tick:
            should_cancel = True

        # Ensure all are cancelled before
        if self.alpaca.is_connected() and should_cancel:

            if self.cancel_thread_running:
                return

            self.cancel_thread_running = True
            self.cancel_update_event.clear()

            threading.Thread(
                target=self._cancellation_worker,
                daemon=True
            ).start()


    def _cancellation_worker(self):
        try:
            with self.cancel_update_lock:
                self.alpaca.cancel_all_orders()
                self.cancelled = True
        except Exception as e:
            Logger.log_error(f"Order cancels failed: {e}")
        finally:
            self.cancel_thread_running = False
            self.cancel_update_event.set()


    def algorithm_tick(self):
        if not Config.can_run: return
        if not self.alpaca.is_connected(): return
        if not self.portfolio_update_event.is_set(): return
        elif not self.algorithm_enabled: 
            self.enable_algorithm()
            self.algorithm_enabled = True
                
        now = time.time()

        if self.extended_hours:
            if now - self.algorithm.extended_tick_rate > self.last_extended_tick:
                self.last_extended_tick = now
                self.cancelled = False
            else: return

            self.prep_algorithm()
            self.algorithm.extended_algorithm_tick()

        else:
            if now - self.algorithm.tick_rate > self.last_tick:
                self.last_tick = now
                self.cancelled = False
            else: return

            self.prep_algorithm()
            self.algorithm.algorithm_tick()


    def prep_algorithm(self):
        # You must lock quote prices on every tick
        self.live_data.lock_quotes()
        self.portfolio.handle_trade_updates(self.live_data.get_trades())
    

    def enable_algorithm(self):
        if self.alpaca.is_connected():
            self.portfolio.reconnect()
    

    def initialize(self):
        NonVolatile.load()
        Config.load(self.algorithm)
        Config.set_et(self.et)
        Logger.set_ux(self.trayd_ux)
        Logger.set_terminal(self.terminal)
        Logger.set_using_terminal(self.using_terminal)

        self.alpaca.initialize()
        self.portfolio_update_event.set()

        if self.has_gui:
            self.trayd_ux.initialize(self.algorithm.name)

        if self.using_terminal:
            self.terminal.start_listen()

        self.live_data.initialize_indicators()
        self.live_data.set_bar_callback_handler(self.algorithm.on_bar_data)
        self.live_data.set_extended_bar_callback_handler(self.algorithm.on_extended_bar_data)

        symbols = self.index.get_symbols()
        self.live_data.start_extended_hour_updates(symbols)

        self.live_data.start_stock_stream(symbols[: min(30, len(symbols))])
        if len(symbols) > 30:
            self.using_data_stream = True
            self.live_data.start_stock_data_stream(symbols[30 : len(symbols)])
        if len(symbols) > 60:
            Logger.log_error("Not enough accounts for quote tracking")

        self.live_data.start_trading_stream()


    def on_exit(self):
        if self.using_terminal:
            self.terminal.stop_listen()

        if self.alpaca.is_connected():
            self.alpaca.cancel_all_orders()

        self.alpaca.stop_api_thread()
        
        self.algorithm.exit()
        self.live_data.close()
        NonVolatile.save()
        Config.save()

        Logger.log_event("EXITING PROGRAM")


    def validate(self):
        if time.time() - Config.validation_rate > self.last_validation:
            self.print("VALIDATING")
            self.last_validation = time.time()
        else: return

        if not self.live_data.extended_trades_running():
            self.live_data.start_extended_hour_updates()

        today = datetime.now(self.et).date()
        if today != self.current_day:
            self.current_day = today
            self.portfolio.new_day()

        # if not self.live_data.trade_stream_running():
        #     Logger.log_error("TRADE STREAM LOST -- RESTARTING")
        #     self.live_data.start_trading_stream()


        # orders = self.alpaca.get_all_orders()
        # if orders and len(orders) != 0: Logger.log_error("ORDERS EXIST DURING VALIDATION")


    def secondary_validation(self):
        if time.time() - Config.secondary_validation_rate > self.last_secondary_validation:
            self.last_secondary_validation = time.time()
        else: return

        self.compare_account_info()
        self.compare_positions()


    def compare_account_info(self):
        pass


    def compare_positions(self):
        pass


    def print(self, msg: str):
        if not self.using_terminal and self.can_output:
            print(msg)

    
    def handle_user_input(self):
        if self.terminal.is_empty(): return

        original = self.terminal.query_next()
        command = original.strip().upper()
        if command == "UX" and self.has_gui:
            if not self.trayd_ux.is_running(): 
                Logger.log_message("Starting user interface...")
                self.trayd_ux.restart(self.algorithm.name)
                self.trayd_ux.set_connected(self.connected)
                self.trayd_ux.set_extended(self.extended_hours)
            else:
                Logger.log_message("User interface already running")

        elif command == "QUIT":
            self.running = False

        elif command == "":
            pass
        
        else:
            Logger.log_message(f"Unknown command: {original}")

        # if self.trayd_ux.is_running():
        #     self.trayd_ux.log(command)



