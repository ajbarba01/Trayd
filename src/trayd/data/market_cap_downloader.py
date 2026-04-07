import requests
import pandas as pd

from trayd.util import Logger
from trayd.config import FMP_API_KEY
from .parquet_downloader import ParquetDownloader
from .granularity import Granularity


class MarketCapDownloader(ParquetDownloader):
    def __init__(self, cache_path: str, data_path: str):
        super().__init__(cache_path, "", Granularity.DAY, data_path=data_path)
        self.api_key = FMP_API_KEY

    def _fetch_market_cap(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Fetch historical market cap data from FMP API for a given symbol and date range."""
        url = (
            f"https://financialmodelingprep.com/stable/historical-market-capitalization"
            f"?symbol={symbol}&apikey={self.api_key}&from={start_date}&to={end_date}"
        )
        headers = {"User-Agent": "Mozilla/5.0"}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            Logger.log_error(f"{symbol}: Error fetching market cap data: {e}")
            return pd.DataFrame()

        data = response.json()
        if not data:
            Logger.log_message(f"No market cap data returned for {symbol}")
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        return df

    def download_all(self, symbols: list[str], start_date: str, end_date: str):
        """Download market cap data for multiple symbols and save as Parquet."""
        self.pbar.start(symbols)

        try:
            for symbol in symbols:
                try:
                    df = self._fetch_market_cap(symbol, start_date, end_date)
                    if df.empty:
                        self.pbar.next()
                        continue

                    # Merge with old data if exists
                    df = self.merge_with_old(symbol, df)

                    # Save as Parquet
                    path = self.get_path(symbol)
                    df.to_parquet(path)

                    # Update cache
                    self._update_cache(symbol, start_date, end_date)
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
