from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.live import StockDataStream
from alpaca.trading.stream import TradingStream

from live.Config import Config
from live.Logger import Logger

import threading
import time


class Alpaca:
    def __init__(self):
        self.trading_client = None
        self.api_thread = None
        self.connected = False
        self.backoff_time = 5.0
        self.halted = False

        self.rest_lock = threading.Lock()


    def is_connected(self) -> bool:
        return self.api_thread and self.api_thread.is_alive() and self.connected


    def start_api_thread(self):
        self.api_thread = threading.Thread(target=self.main_loop, daemon=True)
        self.api_thread.start()

    def stop_api_thread(self):
        self.halted = True

    def main_loop(self):
        while not self.halted:
            self._ensure_connection()

    def close_all_positions(self):
        self.trading_client.close_all_positions()


    def _ensure_connection(self):
        if not self.connected:
            if not self.api_thread or not self.api_thread.is_alive():
                self.start_api_thread()
            
            # Logger.log_message("Connection failure. Retrying...")
            if not self.trading_client:
                self.trading_client = self.get_trading_client()
            
            if self.trading_client:
                try:
                    self.trading_client.get_account()
                    self.connected = True
                except:
                    self.connected = False
            
            if not self.connected: time.sleep(self.backoff_time)
            else: self.connection_found()


    def connection_found(self):
        Logger.log_message("Connected to Alpaca API")


    def connection_lost(self):
        self.connected = False
        Logger.log_error(f"Connection to Alpaca lost")


    def initialize(self):
        self.trading_client = self.get_trading_client()
        self.start_api_thread() 

    # --- Orders ---
    def buy_FOK(self, symbol: str, price_per: float, shares: int):
        with self.rest_lock:
            try:
                limit_order_data = LimitOrderRequest(
                    symbol=symbol,
                    limit_price=price_per,
                    qty=shares,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.FOK,
                    extended_hours=Config.extended_hours
                )
                return self.trading_client.submit_order(limit_order_data)
            except Exception as e:
                Logger.log_error(f"Failed to submit FOK BUY order: {e}")
                return None

    def sell_FOK(self, symbol: str, price_per: float, shares: int):
        with self.rest_lock:
            try:
                limit_order_data = LimitOrderRequest(
                    symbol=symbol,
                    limit_price=price_per,
                    qty=shares,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.FOK,
                    extended_hours=Config.extended_hours
                )
                return self.trading_client.submit_order(limit_order_data)
            except Exception as e:
                Logger.log_error(f"Failed to submit FOK SELL order: {e}")
                return None

    def buy_limit(self, symbol: str, price_per: float, shares: int):
        with self.rest_lock:
            try:
                limit_order_data = LimitOrderRequest(
                    symbol=symbol,
                    limit_price=price_per,
                    qty=shares,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY
                )
                return self.trading_client.submit_order(limit_order_data)
            except Exception as e:
                Logger.log_error(f"Failed to submit LIMIT BUY order: {e}")
                return None

    def sell_limit(self, symbol: str, price_per: float, shares: int):
        with self.rest_lock:
            try:
                limit_order_data = LimitOrderRequest(
                    symbol=symbol,
                    limit_price=price_per,
                    qty=shares,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                )
                return self.trading_client.submit_order(limit_order_data)
            except Exception as e:
                Logger.log_error(f"Failed to submit LIMIT SELL order: {e}")
                return None
        
    def buy_market(self, symbol: str, shares: int):
        with self.rest_lock:
            try:
                market_order_data = MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY
                )
                return self.trading_client.submit_order(market_order_data)
            except Exception as e:
                Logger.log_error(f"Failed to submit MARKET BUY order: {e}")
                return None
        
    def sell_market(self, symbol: str, shares: int):
        with self.rest_lock:
            try:
                limit_order_data = MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY
                )
                return self.trading_client.submit_order(limit_order_data)
            except Exception as e:
                Logger.log_error(f"Failed to submit MARKET BUY order: {e}")
                return None

    # --- Account / Orders ---
    def get_all_orders(self):
        with self.rest_lock:
            try:
                return self.trading_client.get_orders()
            except Exception as e:
                Logger.log_error(f"Failed to get all orders: {e}")
                self.connection_lost()
                return {}

    def cancel_all_orders(self):
        with self.rest_lock:
            try:
                self.trading_client.cancel_orders()
            except Exception as e:
                self.connection_lost()
                Logger.log_error(f"Failed to cancel all orders: {e}")
                return False
        
            return True
    
    def cancel_order(self, order_id: str):
        with self.rest_lock:
            try:
                self.trading_client.cancel_order_by_id(order_id)
            except Exception as e:
                self.connection_lost()
                Logger.log_error(f"Failed to cancel order: {e}")
                return False
        
            return True

    def get_account_info(self):
        with self.rest_lock:
            try:
                return self.trading_client.get_account()
            except Exception as e:
                Logger.log_error(f"Failed to get account info: {e}")
                self.connection_lost()
                return None

    def get_positions(self):
        with self.rest_lock:
            try:
                return self.trading_client.get_all_positions()
            except Exception as e:
                Logger.log_error(f"Failed to get positions: {e}")
                self.connection_lost()
                return []

    # --- Client / Streams ---
    def get_trading_client(self):
        try:
            return TradingClient(Config.API_KEY, Config.SECRET_KEY)
        except:
            Logger.log_error(f"Failed to get trading client")
            self.connection_lost()
            return None

    def get_stock_stream(self):
        try:
            return StockDataStream(Config.API_KEY, Config.SECRET_KEY)
        except:
            Logger.log_error(f"Failed to get stock stream")
            self.connection_lost()
            return None
        
    def get_stock_data_stream(self):
        try:
            return StockDataStream(Config.DATA_API_KEY, Config.DATA_SECRET_KEY)
        except:
            Logger.log_error(f"Failed to get second stock stream")
            self.connection_lost()
            return None
    
    def get_trade_stream(self):
        try:
            return TradingStream(Config.API_KEY, Config.SECRET_KEY)
        except:
            Logger.log_error(f"Failed to get trade stream")
            self.connection_lost()
            return None

