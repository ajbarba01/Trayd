from .granularity import Granularity

from trayd.util import Logger, ProgressBar, get_path

import pandas as pd
import os
import json
import datetime
from datetime import datetime, timedelta


class ParquetDownloader:
    def __init__(
        self,
        cache_path: str,
        data_dir: str,
        granularity: Granularity,
        data_path: str = None,
    ):
        self.granularity = granularity

        self.cache_path: str = cache_path
        self.data_dir: str = data_dir
        if not data_path:
            self.data_path: str = get_path(self.data_dir, f"{granularity}_data")
        else:
            self.data_path = data_path

        self.data_cache: dict[str, dict[str, str]] = {}
        self.cache_updates: dict[str, dict[str, str]] = {}

        self.pbar = ProgressBar(f"Downloading {self.granularity} data")

        self._load_cache()
        self._load_config()

    def download_all(self, symbols: list[str], start_date: str, end_date: str):
        pass

    def query_all(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> bool:
        end_dt = datetime.fromisoformat(end_date).date()
        yesterday = (datetime.today()).date()

        # Cap end_date to today
        if end_dt > yesterday:
            end_dt = yesterday
            end_date = end_dt.isoformat()  # convert back to string

        need_to_download: list[str] = [
            symbol
            for symbol in symbols
            if self._needs_download(symbol, start_date, end_date)
        ]

        if need_to_download:
            # Logger.log_message("Needs to download: ", need_to_download)
            self.download_all(need_to_download, start_date, end_date)

    def merge_with_old(self, symbol: str, new_df: pd.DataFrame):
        path: str = self.get_path(symbol)

        # If old data exists, load and merge
        if os.path.exists(path):
            old_df: pd.DataFrame = pd.read_parquet(path)

            # Combine old + new, drop duplicates
            sym_df_combined: pd.DataFrame = pd.concat([old_df, new_df])
            sym_df_combined = sym_df_combined[
                ~sym_df_combined.index.duplicated(keep="last")
            ]
            sym_df_combined = sym_df_combined.sort_index()
        else:
            sym_df_combined = new_df

        return sym_df_combined

    def delete_all(self, symbols: list[str]):
        for symbol in symbols:
            path = self.get_path(symbol)
            if os.path.exists(path):
                os.remove(path)

    def get_path(self, symbol: str) -> str:
        return get_path(self.data_path, f"{symbol}.parquet")

    def refresh_metadata(self):
        new_cache: dict[str, dict[str, str]] = {}

        # Loop through all files in the data directory
        for filename in os.listdir(self.data_path):
            if not filename.endswith(".parquet"):
                continue

            symbol: str = filename.replace(".parquet", "")
            path: str = get_path(self.data_path, filename)

            try:
                df: pd.DataFrame = pd.read_parquet(path)

                # Ensure index is datetime
                if not pd.api.types.is_datetime64_any_dtype(df.index):
                    df.index = pd.to_datetime(df.index)

                if df.empty:
                    Logger.log_error(f"{symbol}: empty dataframe, skipping")
                    continue

                start_date: str = str(df.index.min().date())
                end_date: str = str(df.index.max().date())

                new_cache[symbol] = {"start": start_date, "end": end_date}

            except Exception as e:
                Logger.log_error(f"Failed to process {symbol}: {e}")
                continue

        # Save the new cache
        self._save_cache(new_cache)

    def _load_config(self):
        return

    def _load_cache(self):
        if os.path.exists(self.cache_path):
            with open(self.cache_path, "r") as fp:
                self.data_cache = json.load(fp)
        else:
            self.data_cache = {}

    def _update_cache(self, symbol: str, new_start: str, new_end: str):
        if symbol in self.data_cache:
            old_start: str = self.data_cache[symbol]["start"]
            old_end: str = self.data_cache[symbol]["end"]

            # Take the earliest start and latest end
            start_date: str = min(old_start, new_start)
            end_date: str = max(old_end, new_end)
        else:
            start_date: str = new_start
            end_date: str = new_end

        self.cache_updates[symbol] = {"start": start_date, "end": end_date}

    def _save_cache(self, new_cache: dict[str, dict[str, str]]):
        tmp: str = self.cache_path + ".tmp"
        with open(tmp, "w") as fp:
            json.dump(new_cache, fp, indent=4)
        os.replace(tmp, self.cache_path)

    def _needs_download(
        self, symbol: str, start_date: str, end_date: str
    ) -> bool:
        start: datetime.date = self._to_date(start_date)
        end: datetime.date = self._to_date(end_date)

        if symbol not in self.data_cache:
            return True

        meta: dict[str, str] = self.data_cache[symbol]
        cache_start: datetime.date = self._to_date(meta["start"])
        cache_end: datetime.date = self._to_date(meta["end"])

        needs_download: bool = start < cache_start or end > cache_end

        return needs_download

    def _to_date(self, s: str) -> datetime.date:
        return datetime.fromisoformat(s).date()
