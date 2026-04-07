from .parquet_downloader import ParquetDownloader
from .granularity import Granularity

from trayd.util import Logger

from contextlib import redirect_stdout, redirect_stderr

import yfinance as yf
import pandas as pd

import os
import io


class YFDownloader(ParquetDownloader):
    def __init__(self, cache_path, data_dir):
        super().__init__(cache_path, data_dir, Granularity.DAY)


    def download_all(self, symbols: list[str], start_date: str, end_date: str):
        if self.granularity == Granularity.INTRADAY: return
        
        if not symbols:
            return

        os.makedirs(self.data_dir, exist_ok=True)

        num_failed = 0

        # Download all at once
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            df_new: pd.DataFrame = yf.download(
                tickers=symbols,
                start=start_date,
                end=end_date,
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False,
            )


        for symbol in symbols:
            # Extract symbol DataFrame
            sym_df_new: pd.DataFrame = df_new[symbol] if isinstance(df_new.columns, pd.MultiIndex) else df_new
            sym_df_new = sym_df_new.dropna(how="all")

            if sym_df_new.empty:
                # Logger.log_error(f"{symbol}: empty dataframe")
                num_failed += 1
                continue

            path: str = self.get_path(symbol)

            sym_df_new = sym_df_new.sort_index()

            sym_df_combined = self.merge_with_old(symbol, sym_df_new)

            sym_df_combined.to_parquet(path)

            self._update_cache(symbol, start_date, end_date)

        if num_failed > 0:
            Logger.log_message(f"{num_failed} symbols failed to download.")

        # Save updated cache
        if self.cache_updates:
            self.data_cache.update(self.cache_updates)
            self._save_cache(self.data_cache)