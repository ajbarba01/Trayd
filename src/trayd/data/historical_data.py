from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from queue import Queue
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from trayd.util import Logger, ProgressBar

from .data_query import DataQuery
from .granularity import Granularity
from .ohlcv import OHLCV

if TYPE_CHECKING:
    from trayd.indicators import Indicator
    

class HistoricalData:
    def __init__(self, granularity: Granularity = Granularity.DAY):
        self.data_query: DataQuery = DataQuery(granularity)
        self.symbols: list[str] = []
        self.symbols_set: set[str] = set()
        self.symbol_index: dict[str, int] = {}  # symbol -> index

        self.bar_data: np.ndarray  # shape: (num_symbols, num_timestamps, 5)
        self.indicator_data: np.ndarray  # shape: (num_symbols, num_indicators, num_timestamps)
        self.num_indicators: int = 0
        self.indicators: list[Indicator] = []
        self.indicator_registry: dict[str, Indicator] = {}

        self.global_timestamps: pd.DatetimeIndex
        self.current_ts_idx: int = 0
        self.current_ts: pd.Timestamp = None
        self.current_valid_mask: np.ndarray  = None

        self.delist_times: dict[pd.Timestamp, list[str]] = {}
        self.just_delisted: list[str] = []

        self.warmup_window: int = 20

        self.granularity: Granularity = granularity
        self.time_deltas: dict[Granularity, pd.Timedelta] = {
            Granularity.DAY: pd.Timedelta(days=1),
            Granularity.INTRADAY: pd.Timedelta(minutes=5),
        }

        self.intraday = self.granularity == Granularity.INTRADAY

        self.offset_offset = 1 if granularity == Granularity.DAY else 0

        self.pbar = ProgressBar(f"Loading {self.granularity} data")

    def add_window_padding(self, window_padding: int):
        self.warmup_window += window_padding + 1

    def is_finished(self) -> bool:
        return self.current_ts_idx + 1 >= len(self.global_timestamps)

    def next(self) -> pd.Timestamp:
        self.current_ts_idx += 1
        self.current_ts = self.global_timestamps[self.current_ts_idx]

        # Mask for valid symbols at this timestamp
        self.current_valid_mask = self._compute_valid_mask(self.current_ts_idx)

        if self.current_ts in self.delist_times:
            self.just_delisted += self.delist_times[self.current_ts] 

        return self.current_ts
    
    def skip(self) -> pd.Timestamp:
        self.current_ts_idx += 1
        self.current_ts = self.global_timestamps[self.current_ts_idx]

        if self.current_ts in self.delist_times:
            self.just_delisted = self.delist_times[self.current_ts] 

        return self.current_ts
    
    def get_delisted(self) -> list[str]:
        delisted = self.just_delisted.copy()
        self.just_delisted.clear()

        return delisted


    def add_indicator(self, ind: Indicator):
        sig = ind.signature

        if sig in self.indicator_registry:
            return self.indicator_registry[sig]
        
        resolved_reqs = []
        for req in ind.get_prereqs():
            existing = self.add_indicator(req)
            resolved_reqs.append(existing)

        ind.dependencies = resolved_reqs

        ind.key = self.num_indicators
        self.num_indicators += 1
        self.indicator_registry[sig] = ind
        self.indicators.append(ind)
        Logger.log_message(f"Added {self.granularity} indicator: {sig}")

        if ind.get_warmup_window() > self.warmup_window:
            self.warmup_window = ind.get_warmup_window()

        return ind


    def load_all(self, symbols: dict[str, pd.Timestamp], start_date: str, end_date: str, max_workers: int = 20):
        self.pbar.start(list(symbols.keys()), 10)

        symbols_list = list(symbols.keys())
        self.symbols = symbols_list
        self.symbols_set = set(symbols_list)
        self.symbol_index = {s: i for i, s in enumerate(symbols_list)}

        target_start = pd.Timestamp(start_date)
        start_date = self._n_ticks_before(start_date, self.warmup_window * 2)
        start_date_ts = pd.Timestamp(start_date)

        # Query all data first
        self.data_query.query_all(symbols_list, start_date, end_date)

        loaded_data = []
        all_ts = pd.DatetimeIndex([])

        to_delete = Queue()

        # Worker function to load a single symbol
        def load_symbol(symbol, symbol_start):
            if not symbol_start:
                symbol_start = pd.Timestamp(start_date)
            symbol_start = symbol_start - timedelta(self.warmup_window * 2)
            symbol_start = max(start_date_ts, symbol_start)
            path = self.data_query.get_path(symbol)
            if not os.path.exists(path):
                # Logger.log_error(f"{symbol}: Parquet file not found")
                return None
            df = pd.read_parquet(path).sort_index()
            df = df.loc[symbol_start:end_date]
            if df.empty:
                # Logger.log_error(f"{symbol}: no data in range")
                to_delete.put(symbol)
                return None
            df.index = pd.to_datetime(df.index)
            return symbol, df

        # Launch threads
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol = {executor.submit(load_symbol, symbol, symbol_start): symbol for symbol, symbol_start in symbols.items()}
            for future in as_completed(future_to_symbol):
                result = future.result()
                self.pbar.next()
                if result:
                    symbol, df = result
                    loaded_data.append((symbol, df))
                    delist_time = max(df.index)
                    self.add_delist_time(symbol, delist_time)
                    all_ts = all_ts.union(df.index)

        list_to_del = []
        while not to_delete.empty():
            list_to_del.append(to_delete.get())

        if list_to_del:
            print("NEED TO DELETE", list_to_del)

        self.global_timestamps = all_ts
        num_symbols = len(symbols_list)
        num_timestamps = len(self.global_timestamps)

        # Preallocate bar data array: (symbols, timestamps, OHLCV)
        if self.intraday:
            bar_length = 6
        else:
            bar_length = 5

        self.bar_data = np.full((num_symbols, num_timestamps, bar_length), np.nan, dtype=np.float64)

        # Fill bar data using vectorized indexing
        for symbol, df in loaded_data:
            i = self.symbol_index[symbol]
            idx = np.searchsorted(self.global_timestamps, df.index.values)
            self.bar_data[i, idx, OHLCV.OPEN] = df["Open"].to_numpy()
            self.bar_data[i, idx, OHLCV.HIGH] = df["High"].to_numpy()
            self.bar_data[i, idx, OHLCV.LOW] = df["Low"].to_numpy()
            self.bar_data[i, idx, OHLCV.CLOSE] = df["Adj Close"].to_numpy()
            self.bar_data[i, idx, OHLCV.VOLUME] = df["Volume"].to_numpy()

            if self.intraday:
                self.bar_data[i, idx, OHLCV.VWAP] = df["VWAP"].to_numpy()

        # Initialize indicator array (empty for now)
        self.indicator_data = np.empty((num_symbols, self.num_indicators, num_timestamps), dtype=np.float64)
        self.indicator_data.fill(np.nan)

        # Start index
        self.current_ts_idx = max(np.searchsorted(self.global_timestamps, target_start), self.warmup_window - 1)
        self.current_ts = self.global_timestamps[self.current_ts_idx]
        self.current_valid_mask = ~np.isnan(self.bar_data[:, self.current_ts_idx, OHLCV.CLOSE])

        self.load_indicators()
        self.pbar.stop()

    def add_delist_time(self, symbol: str, timestamp: pd.Timestamp):
        if symbol in self.delist_times:
            self.delist_times[timestamp].append(symbol)
        else:
            self.delist_times[timestamp] = [symbol]


    def load_indicators(self):
        # Logger.log_message("WARMUP WINDOW:", self.warmup_window)
        for ind in self.indicators:
            ind.indicator_data = self.indicator_data
            ind.historical = self
            ind.compute()

    # Fast accessors
    def _get_symbol_idx(self, symbol: str) -> int:
        return self.symbol_index[symbol]

    def get_open(self, symbol: str, offset: int = 0) -> float:
        return self.bar_data[self._get_symbol_idx(symbol), self.current_ts_idx + offset - self.offset_offset, OHLCV.OPEN]

    def get_high(self, symbol: str, offset: int = 0) -> float:
        return self.bar_data[self._get_symbol_idx(symbol), self.current_ts_idx + offset - self.offset_offset, OHLCV.HIGH]

    def get_low(self, symbol: str, offset: int = 0) -> float:
        return self.bar_data[self._get_symbol_idx(symbol), self.current_ts_idx + offset - self.offset_offset, OHLCV.LOW]

    def get_close(self, symbol: str, offset: int = 0) -> float:
        return self.bar_data[self._get_symbol_idx(symbol), self.current_ts_idx + offset - self.offset_offset, OHLCV.CLOSE]

    def get_volume(self, symbol: str, offset: int = 0) -> float:
        return self.bar_data[self._get_symbol_idx(symbol), self.current_ts_idx + offset - self.offset_offset, OHLCV.VOLUME]
    
    def get_VWAP(self, symbol: str, offset: int = 0) -> float:
        return self.bar_data[self._get_symbol_idx(symbol), self.current_ts_idx + offset - self.offset_offset, OHLCV.VWAP]

    def has_bar(self, symbol: str, offset: int = 0) -> bool:
        i = self._get_symbol_idx(symbol)
        return self.current_valid_mask[i + offset - self.offset_offset]

    def get_indicator_data(self, symbol: str, key: int, offset: int = 0) -> float:
        i = self._get_symbol_idx(symbol)
        return self.indicator_data[i, key, self.current_ts_idx + offset - self.offset_offset]
    
    def is_valid(self, symbol: str) -> bool:
        i = self.symbol_index.get(symbol)
        if i is None:
            return False

        return bool(self.current_valid_mask[i])
    
    def _compute_valid_mask(self, ts_idx: int) -> np.ndarray:
        w = self.warmup_window

        # Not enough global history yet
        if ts_idx < w - 1:
            return np.zeros(len(self.symbols), dtype=bool)

        window = self.bar_data[
            :, 
            ts_idx - w + 1 : ts_idx + 1, 
            OHLCV.CLOSE
        ]

        return np.all(~np.isnan(window), axis=1)

    # Helper
    def _n_ticks_before(self, date_str: str, n: int) -> str:
        timedelt = self.time_deltas[self.granularity]
        d: datetime.date = datetime.fromisoformat(date_str).date()
        new_d: datetime.date = d - timedelt * n
        return str(new_d)
