from polygon import RESTClient
import pandas as pd
from datetime import datetime
import os
import time

from .parquet_downloader import ParquetDownloader
from .granularity import Granularity
from trayd.util import Logger
from trayd.config import POLYGON_API_KEY

from datetime import timedelta
from tqdm import tqdm


class PolygonDownloader(ParquetDownloader):
    def __init__(self, cache_path, data_dir):
        super().__init__(cache_path, data_dir, Granularity.INTRADAY)
        self.api_key = POLYGON_API_KEY
        self.client = RESTClient(api_key=self.api_key)
        self.multiplier = 5
        self.timespan = "minute"
        self.max_yrs = 5

    # ---------- DOWNLOAD METHOD ----------
    def download_all(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        intraday_only: bool = True,
    ):
        return
        os.makedirs(self.data_dir, exist_ok=True)
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)

        five_years_ago = datetime.utcnow() - timedelta(days=self.max_yrs * 365)
        if start_dt < five_years_ago:
            Logger.log_message(
                f"Intraday start date {start_dt.date()} is older than 5 years ago."
            )

        # Initialize progress bar
        self.pbar.start(symbols)

        try:
            for symbol in symbols:
                try:
                    all_bars = []
                    for bar in self.client.list_aggs(
                        ticker=symbol,
                        multiplier=self.multiplier,
                        timespan=self.timespan,
                        from_=start_dt.strftime("%Y-%m-%d"),
                        to=end_dt.strftime("%Y-%m-%d"),
                        limit=40000,
                    ):
                        all_bars.append(bar)

                    if not all_bars:
                        self.pbar.next()
                        continue

                    df = pd.DataFrame(
                        [
                            {
                                "Open": b.open,
                                "High": b.high,
                                "Low": b.low,
                                "Adj Close": b.close,
                                "Volume": b.volume,
                                "VWAP": b.vwap,
                                "t": datetime.fromtimestamp(b.timestamp / 1000),
                            }
                            for b in all_bars
                        ]
                    )

                    df = df.set_index("t").sort_index()

                    if intraday_only:
                        df = df.between_time("09:30", "16:00")

                    df = self.merge_with_old(symbol, df)
                    path = self.get_path(symbol)
                    df.to_parquet(path)

                    self._update_cache(symbol, start_date, end_date)

                    # Update progress bar
                    self.pbar.next()

                except Exception as e:
                    Logger.log_error(f"{symbol}: {e}")
                    self.pbar.next(symbol)

        except KeyboardInterrupt:
            Logger.log_message(
                "KeyboardInterrupt detected, stopping downloads..."
            )

        finally:
            if self.cache_updates:
                self.data_cache.update(self.cache_updates)
                self._save_cache(self.data_cache)
                self.pbar.stop()
