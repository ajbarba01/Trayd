from alpaca.data.models import Quote, Bar
from alpaca.trading.models import TradeUpdate

import yfinance as yf

from live.Alpaca import Alpaca
from live.Logger import Logger
from live.Config import Config
from live.Index import Index

from live.Indicator import Indicator
from i_RSI import RSI
from i_EMA import EMA
from i_MACD import MACD

from live.helpers import is_within_seconds

from dataclasses import dataclass

from datetime import datetime, timedelta

import pandas as pd
import yfinance
import asyncio
import threading
import json
import time
import queue
import contextlib
import io


@dataclass
class LocalBar:
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float
    timestamp: datetime


class LiveData:
    def __init__(self, index: Index, alpaca: Alpaca, timezone_data):
        self.index = index
        self.alpaca = alpaca
        self.et = timezone_data
        self.quotes: dict[str, Quote] = {}
        self.locked_quotes = {}
        self.extended_quotes = {}
        self.locked_extended_quotes = {}

        self.thread_lock = threading.Lock()
        self.latest_timestamp = 0.0

        self.trade_updates = queue.Queue()

        self.stock_stream = None
        self.stock_data_stream = None
        self.trade_stream = None

        self.stock_stream_thread = None
        self.stock_data_stream_thread = None
        self.trade_stream_thread = None
        self.extended_hour_thread = None

        self.extended_hours = False

        self.last_extended_query = 0.0

        self.bar_lock = threading.Lock()
        self.bars: dict[str, tuple[LocalBar, str]] = {}
        self.bar_callback_handler = None
        self.extended_bar_callback_handler = None
        self.minute_granularity: int = 5

        # Indicators
        self.rsi: dict[str, RSI] = {}
        self.ema: dict[str, EMA] = {}
        self.macd: dict[str, MACD] = {}

        self.indicators: list[Indicator] = [RSI, EMA, MACD]

        self.indicators_initialized = False
        self.initializing_indicators = False
        self.last_ind_update = None


    def floor_to_granularity(self, dt: datetime) -> datetime:
        # number of minutes since the start of the hour
        minutes = (dt.minute // self.minute_granularity) * self.minute_granularity
        return dt.replace(minute=minutes, second=0, microsecond=0)


    def initialize_indicators(self):
        if self.initializing_indicators: return
        if self.floor_to_granularity(datetime.now()) == self.last_ind_update: return

        self.initializing_indicators = True
        self.indicators_initialized = False

        symbols = self.index.get_symbols()
        for symbol in symbols:
            self.rsi[symbol] = RSI(symbol, self.minute_granularity)
            self.ema[symbol] = EMA(symbol, self.minute_granularity)
            self.macd[symbol] = MACD(symbol, self.minute_granularity)

        bars_needed = max([ind("NULL", self.minute_granularity).warmup_time for ind in self.indicators])

        def _initialize_indicators():
            # with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            data = yf.download(
                tickers=symbols,
                interval="1m",
                period="5d",
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False,
                prepost=True
            )

            bars = {}
            for symbol in symbols:
                if symbol not in data:
                    Logger.log_error(f"Couldn't initialize {symbol} indicators")

                df = data[symbol].dropna()
                if len(df) >= bars_needed:
                    bars[symbol] = df.tail(bars_needed * self.minute_granularity * 2)
                else:
                    Logger.log_error(f"Couldn't fully initialize {symbol} indicators")
                    bars[symbol] = df  # return what we have

            for symbol, df in bars.items():
                for ts, close in df["Close"].items():
                    # ensure timezone-aware
                    if ts.tzinfo is None:
                        ts = ts.tz_localize("UTC")  # Yahoo returns UTC by default
                    ts = ts.tz_convert(self.et)          # convert to Eastern Time

                    timestamp = ts.to_pydatetime()
                    close = float(close)

                    self.update_indicators(symbol, timestamp, close)

            Logger.log_message("Indicators properly initialized")
            Logger.log_message(f"MACD ready: {list(self.macd.values())[0].is_ready()}")
            Logger.log_message(f"EMA ready: {list(self.ema.values())[0].is_ready(50)}")
            Logger.log_message(f"RSI ready: {list(self.rsi.values())[0].is_ready()}")

            self.indicators_initialized = True
            self.initializing_indicators = False


        thread = threading.Thread(target=_initialize_indicators, daemon=True)
        thread.start()


    def set_bar_callback_handler(self, bar_handler):
        self.bar_callback_handler = bar_handler


    def set_extended_bar_callback_handler(self, bar_handler):
        self.extended_bar_callback_handler = bar_handler


    def set_extended_hours(self):
        self.extended_hours = True


    def set_normal_hours(self):
        self.extended_hours = False


    # --- Quotes Locking ---
    def lock_quotes(self):
        with self.thread_lock:
            if self.extended_hours:
                self.locked_extended_quotes = self.extended_quotes.copy()

            else:
                self.locked_quotes = self.quotes.copy()

                # Clear quotes so that no stale data is used next tick
                self.quotes.clear()


    def start_extended_hour_updates(self, symbols: list[str]):
        if self.extended_hour_thread and self.extended_hour_thread.is_alive():
            return  # already running

        def run_thread():
            while True:
                try:
                    if self.extended_hours and self.alpaca.is_connected():
                        self.query_extended_data(symbols)
                    time.sleep(Config.extended_tick_rate)
                except Exception as e:
                    Logger.log_error(f"Extended hours thread error: {e}")
                    time.sleep(1)  # avoid tight loop on error

        thread = threading.Thread(target=run_thread, daemon=True)
        thread.start()
        self.extended_hour_thread = thread


    def query_extended_data(self, symbols: list[str]):
        if not self.indicators_initialized: return  

        self.extended_quotes.clear()
        now = datetime.now(self.et)
        five_minutes_ago = now - timedelta(minutes=5)

        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                data = yfinance.download(
                    tickers=" ".join(symbols),
                    interval="1m",
                    period="1d",
                    prepost=True,
                    auto_adjust=False,
                    group_by="ticker",
                    threads=True,
                    progress=False
                )
        except Exception as e:
            Logger.log_error(f"Batch download failed: {e}")
            return

        if data is None or data.empty:
            return

        def process_symbol(symbol: str, df: pd.DataFrame):
            df = df.dropna(subset=["Close"])
            if df.empty:
                return

            # Latest bar timestamp
            latest_time = df.index[-1]
            if latest_time.tzinfo is None:
                latest_time = latest_time.tz_localize("UTC").tz_convert(self.et)
            else:
                latest_time = latest_time.tz_convert(self.et)

            if latest_time >= five_minutes_ago:
                timestamp = latest_time.to_pydatetime()
                local_bar = self.extended_to_local_bar(symbol, timestamp, df)
                self.extended_bar_handler(local_bar)

        # Multi-symbol download
        if isinstance(data.columns, pd.MultiIndex):
            for symbol in data.columns.levels[0]:
                try:
                    df_symbol = data[symbol]
                    process_symbol(symbol, df_symbol)
                except Exception as e:
                    Logger.log_error(f"Failed to process {symbol}: {e}")
        else:
            # Single-symbol download
            try:
                process_symbol(symbols[0], data)
            except Exception as e:
                Logger.log_error(f"Failed to process {symbols[0]}: {e}")

    
    def extended_to_local_bar(self, symbol: str, timestamp: datetime, df: pd.DataFrame) -> LocalBar:
        last_row = df.iloc[-1]

        open_price = float(last_row["Open"])
        high_price = float(last_row["High"])
        low_price = float(last_row["Low"])
        close_price = float(last_row["Close"])
        volume = float(last_row["Volume"])

        # Simple VWAP approximation for a single bar
        vwap = (open_price + high_price + low_price + close_price) / 4

        return LocalBar(
            symbol=symbol,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            vwap=vwap,
            timestamp=timestamp
        )


    # --- Stock Stream ---
    def start_stock_stream(self, symbols: list[str]):
        if self.stock_stream_thread and self.stock_stream_thread.is_alive():
            return  # already running

        self.watching = set(symbols)

        def run_stream():
            backoff = 1
            while True:
                if not self.alpaca.is_connected(): continue
                try:
                    self.stock_stream = self.alpaca.get_stock_stream()
                    if not self.stock_stream: continue
                    for symbol in symbols:
                        self.stock_stream.subscribe_quotes(self.quote_handler, symbol)
                        self.stock_stream.subscribe_bars(self.bar_handler, symbol)

                    Logger.log_message("Starting stock stream...")
                    asyncio.run(self.stock_stream.run())
                except Exception as e:
                    Logger.log_error(f"Stock stream error: {e}. Retrying in {backoff} seconds.")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)  # exponential backoff up to 60s
                else:
                    break  # clean exit

        thread = threading.Thread(target=run_stream, daemon=True)
        thread.start()
        self.stock_stream_thread = thread


    def end_stock_stream(self):
        if self.stock_stream:
            try:
                asyncio.run(self.stock_stream.stop_ws())
                self.stock_stream.unsubscribe_quotes()
            except Exception as e:
                Logger.log_error(f"Error stopping stock stream: {e}")
            finally:
                self.stock_stream = None
        self.stock_stream_thread = None


    # --- Stock Data Stream ---
    def start_stock_data_stream(self, symbols: list[str]):
        if self.stock_data_stream_thread and self.stock_data_stream_thread.is_alive():
            return  # already running

        self.watching_data_stream = set(symbols)

        def run_stream():
            backoff = 1
            while True:
                if not self.alpaca.is_connected(): 
                    time.sleep(1)
                    continue
                try:
                    self.stock_data_stream = self.alpaca.get_stock_data_stream()
                    if not self.stock_data_stream: 
                        time.sleep(1)
                        continue

                    for symbol in symbols:
                        self.stock_data_stream.subscribe_quotes(self.quote_handler, symbol)
                        self.stock_data_stream.subscribe_bars(self.bar_handler, symbol)

                    Logger.log_message("Starting stock data stream...")
                    asyncio.run(self.stock_data_stream.run())
                except Exception as e:
                    Logger.log_error(f"Stock data stream error: {e}. Retrying in {backoff} seconds.")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)  # exponential backoff up to 60s
                else:
                    break  # clean exit

        thread = threading.Thread(target=run_stream, daemon=True)
        thread.start()
        self.stock_data_stream_thread = thread


    def end_stock_data_stream(self):
        if self.stock_data_stream:
            try:
                asyncio.run(self.stock_data_stream.stop_ws())
                self.stock_data_stream.unsubscribe_quotes()
            except Exception as e:
                Logger.log_error(f"Error stopping stock data stream: {e}")
            finally:
                self.stock_data_stream = None
        self.stock_data_stream_thread = None
        self.watching_data_stream.clear()

  
    # --- Trading Stream ---
    def start_trading_stream(self):
        if self.trade_stream_thread and self.trade_stream_thread.is_alive():
            return  # already running

        def run_stream():
            backoff = 1
            while True:
                if not self.alpaca.is_connected(): continue
                try:
                    self.trade_stream = self.alpaca.get_trade_stream()
                    if not self.trade_stream: continue
                    self.trade_stream.subscribe_trade_updates(self.trade_handler)

                    Logger.log_message("Starting trade stream...")
                    asyncio.run(self.trade_stream.run())
                except Exception as e:
                    Logger.log_error(f"Trade stream error: {e}. Retrying in {backoff} seconds.")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                else:
                    break  # clean exit

        thread = threading.Thread(target=run_stream, daemon=True)
        thread.start()
        self.trade_stream_thread = thread


    def end_trade_stream(self):
        if self.trade_stream:
            try:
                asyncio.run(self.trade_stream.stop_ws())
            except Exception as e:
                Logger.log_error(f"Error stopping trade stream: {e}")
            finally:
                self.trade_stream = None
        self.trade_stream_thread = None

    # --- Stream Status ---
    def stock_stream_running(self):
        return self.stock_stream_thread and self.stock_stream_thread.is_alive()
    

    def trade_stream_running(self):
        return self.trade_stream_thread and self.trade_stream_thread.is_alive()
    

    def extended_trades_running(self):
        return self.extended_hour_thread and self.extended_hour_thread.is_alive()


    def update_indicators(self, symbol: str, timestamp: datetime, close: float):
        timestamp = self.floor_to_granularity(timestamp)
        if timestamp.minute % self.minute_granularity == 0:
            self.last_ind_update = timestamp
            self.rsi[symbol].update(timestamp, close)
            self.macd[symbol].update(timestamp, close)
            self.ema[symbol].update(timestamp, close)


    # --- Handlers ---
    async def quote_handler(self, quote: Quote):
        with self.thread_lock:
            self.quotes[quote.symbol] = quote
            self.latest_timestamp = time.time()


    def extended_bar_handler(self, bar: LocalBar):
        if self.extended_hours:
            symbol = bar.symbol
            self.bars[bar.symbol] = (bar, time.time())
            self.update_indicators(symbol, bar.timestamp, bar.close)

            if self.extended_bar_callback_handler and Config.can_run:
                self.extended_bar_callback_handler(bar)


    async def bar_handler(self, bar: Bar):
        local_bar = LocalBar(bar.symbol, bar.open, bar.high, bar.low, bar.close, bar.volume, bar.vwap, bar.timestamp)
        # Logger.log_message(f"{bar.symbol}: {bar.timestamp}")
        with self.bar_lock:
            symbol = bar.symbol
            self.bars[bar.symbol] = (local_bar, time.time())
            self.update_indicators(symbol, bar.timestamp, bar.close)


        if self.bar_callback_handler and Config.can_run:
            self.bar_callback_handler(local_bar)


    async def trade_handler(self, trade: TradeUpdate):
        self.trade_updates.put(trade)


    # --- Data Access ---
    def has_quote(self, symbol: str) -> bool:
        if self.extended_hours:
            return symbol in self.locked_extended_quotes
        else:
            return symbol in self.locked_quotes
        

    def has_bar(self, symbol: str) -> bool:
        return symbol in self.bars and is_within_seconds(self.bars[symbol][1], 1)
    

    def get_bar(self, symbol: str) -> LocalBar:
        return self.bars[symbol][0]
    

    def get_close(self, symbol: str) -> float:
        return self.bars[symbol][0].close


    def get_open(self, symbol: str) -> float:
        return self.bars[symbol][0].open


    def get_high(self, symbol: str) -> float:
        return self.bars[symbol][0].high


    def get_low(self, symbol: str) -> float:
        return self.bars[symbol][0].low


    def get_volume(self, symbol: str) -> float:
        return self.bars[symbol][0].volume


    def get_VWAP(self, symbol: str) -> float:
        return self.bars[symbol][0].vwap
    

    def get_RSI(self, symbol: str) -> RSI:
        return self.rsi[symbol].get()
    

    def get_EMA(self, symbol: str, period: int) -> EMA:
        return self.ema[symbol].get(period)
    

    def get_MACD(self, symbol: str) -> MACD:
        return self.macd[symbol].get()

    
    def get_price(self, symbol: str) -> float:
        if self.extended_hours:
            return self.locked_extended_quotes[symbol]

        else:
            quote: Quote = self.locked_quotes.get(symbol)
            if quote:
                price = (float(quote.bid_price) + float(quote.ask_price)) / 2.0
                return price
            else: return 0
            return float(self.locked_quotes.get(symbol).bid_price)


    def get_quotes(self):
        if self.extended_hours:
            return list(self.locked_extended_quotes.keys())
        else:
            return list(self.locked_quotes.keys())
    

    def get_trades(self):
        return self.trade_updates


    def get_latest_timestamp(self) -> float:
        with self.thread_lock:
            return self.latest_timestamp

    # --- Cleanup ---
    def close(self):
        self.end_stock_stream()
        self.end_trade_stream()


    def clear(self):
        self.quotes.clear()
        self.locked_quotes.clear()
