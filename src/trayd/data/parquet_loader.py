import os
import pandas as pd

from trayd.util import get_path

class ParquetLoader:
    def __init__(self, cache_path: str, data_path: str):
        self.cache_path = cache_path
        self.data_path = data_path
        self.data = {}

    def get_path(self, symbol: str) -> str:
        """Return the full path to a symbol's Parquet file."""
        return get_path(self.data_path, f"{symbol}.parquet")
    
    def has_path(self, symbol: str) -> bool:
        return os.path.exists(self.get_path(symbol))
    
    def load_symbol(self, symbol: str) -> pd.DataFrame:
        """Load a single symbol's Parquet file into memory and cache it."""
        if symbol in self.data:
            return self.data[symbol]  # Already loaded

        file_path = self.get_path(symbol)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Parquet file for {symbol} not found at {file_path}")

        df = pd.read_parquet(file_path)
        self.data[symbol] = df
        return df

    def load_all(self, symbols: list[str], start_date: str = None, end_date: str = None):
        """Load multiple symbols into memory and optionally filter by date range."""
        for symbol in symbols:
            df = self.load_symbol(symbol)

            if start_date:
                df = df[df.index >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df.index <= pd.to_datetime(end_date)]

            # Update the cache with the filtered data
            self.data[symbol] = df

    def load_all_dated(
        self,
        symbols: list[str],
        start_date: str = None,
        end_date: str = None
    ) -> dict[str, dict[pd.Timestamp, dict]]:
        """
        Load multiple symbols and return:
            symbol -> timestamp -> { column_name: value }
        """
        dated_data: dict[str, dict[pd.Timestamp, dict]] = {}

        start_dt = pd.to_datetime(start_date) if start_date else None
        end_dt   = pd.to_datetime(end_date) if end_date else None
            
        failed = 0
        for symbol in symbols:
            if not self.has_path(symbol):
                failed += 1
                continue

            df = self.load_symbol(symbol)

            # FIX: ensure timestamp index
            if "date" in df.columns:
                df = df.copy()
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date")

            # Optional filters
            if start_dt is not None:
                df = df[df.index >= start_dt]
            if end_dt is not None:
                df = df[df.index <= end_dt]

            # FIX: drop symbol column if present
            if "symbol" in df.columns:
                df = df.drop(columns=["symbol"])

            # FINAL STRUCTURE
            dated_data[symbol] = dict(
                zip(df.index, df.to_dict("records"))
            )

        print(f"{failed} symbols failed to load.")
        return dated_data


    def get_data(self, symbol: str):
        """Retrieve data from memory cache. Raises error if not loaded."""
        if symbol not in self.data:
            raise KeyError(f"{symbol} not loaded. Call load_symbol or load_all first.")
        return self.data[symbol]
    
    def has_data(self, symbol: str) -> bool:
        return symbol in self.data
