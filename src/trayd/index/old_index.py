import os
import pandas as pd

from trayd.data import HistoricalData
from trayd.util import get_path


class Index:
    def __init__(self, index_name: str):
        self.index_name = index_name
        self.historical: HistoricalData | None = None
        self.index_start_date: pd.Timestamp | None = None

        # CSV file: symbol,start_date,end_date
        self.index_data_path = get_path("index", "data", f"index_{self.index_name}.csv")
        self.index_data: pd.DataFrame | None = None

        # Maps day -> list of symbols added or removed
        self.adds: dict[pd.Timestamp, list[str]] = {}
        self.removals: dict[pd.Timestamp, list[str]] = {}

        # Symbol start dates
        self.symbol_starts: dict[str, pd.Timestamp] = {}

        # All symbols ever in index
        self.all_symbols: list[str] = []

        # Currently active symbols
        self.current_symbols: set[str] = set()

        # Sorted list of all unique timestamps (day-level)
        self.all_timestamps: list[pd.Timestamp] = []
        self.num_ts: int = 0
        self.current_ts_idx: int = 0

    # --------------------------
    # Loading CSV and preprocessing
    # --------------------------
    def load_all(self, start_date_str: str) -> pd.Timestamp:
        start_date = pd.to_datetime(start_date_str).normalize()
        # Load CSV
        self.index_data = pd.read_csv(self.index_data_path, parse_dates=['start_date', 'end_date'])

        timestamps = set()
        first_timestamp = pd.Timestamp.now().normalize()

        for _, row in self.index_data.iterrows():
            symbol = row['symbol']
            start_ts = pd.Timestamp(row['start_date']).normalize()
            end_ts = pd.Timestamp(row['end_date']).normalize() if pd.notna(row['end_date']) else None

            # Track all symbols
            self.all_symbols.append(symbol)
            self.symbol_starts[symbol] = start_ts

            if start_ts < first_timestamp:
                first_timestamp = start_ts

            # Track adds
            timestamps.add(start_ts)
            self.adds.setdefault(start_ts, []).append(symbol)

            # Track removals
            if end_ts:
                timestamps.add(end_ts)
                self.removals.setdefault(end_ts, []).append(symbol)

        # Sorted timestamps as list of pd.Timestamp
        self.all_timestamps = sorted(timestamps)
        self.num_ts = len(self.all_timestamps)
        self.current_ts_idx = 0

        self.index_start_date = first_timestamp

        # Initialize current_symbols to start date
        self.update_to(start_date)
        if start_date < self.index_start_date:
            print(f"WARNING: {self.index_name} starts after backtest start.")

        return self.index_start_date

    # --------------------------
    # Update current symbols to a specific date
    # --------------------------
    def update_to(self, timestamp: pd.Timestamp):
        ts = pd.Timestamp(timestamp).normalize()

        while self.current_ts_idx < self.num_ts and ts >= self.all_timestamps[self.current_ts_idx]:
            current_day = self.all_timestamps[self.current_ts_idx]

            # Add symbols
            for symbol in self.adds.get(current_day, []):
                self.current_symbols.add(symbol)

            # Remove symbols
            for symbol in self.removals.get(current_day, []):
                self.current_symbols.discard(symbol)

            self.current_ts_idx += 1

    # --------------------------
    # Helper functions
    # --------------------------
    def get_symbol_start(self, symbol: str) -> pd.Timestamp:
        return self.symbol_starts[symbol]

    def initialize(self, historical: HistoricalData):
        self.historical = historical

    def get_valid_symbols(self) -> list[str]:
        return [s for s in self.all_symbols if s in self.current_symbols and self.historical.has_bar(s)]


    def get_all_symbols(self) -> list[str]:
        return self.all_symbols

    # --------------------------
    # String representations
    # --------------------------
    def __repr__(self) -> str:
        return f"<Index {self.index_name}>"

    def __str__(self) -> str:
        return self.index_name
