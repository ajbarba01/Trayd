from .granularity import Granularity
from .parquet_downloader import ParquetDownloader
from .yf_downloader import YFDownloader
from .polygon_downloader import PolygonDownloader

from trayd.util import Logger, get_path

import yfinance as yf
import pandas as pd

import os
import io
import json
from datetime import datetime, timedelta

DOWNLOADERS = {
    Granularity.DAY: YFDownloader,
    Granularity.INTRADAY: PolygonDownloader,
}


class DataQuery:
    def __init__(self, granularity: Granularity):
        self.granularity = granularity
        self.data_dir = "data"
        self.cache_path: str = get_path(
            self.data_dir, "cache", f"{self.granularity}_cache_metadata.json"
        )
        self.downloader: ParquetDownloader = DOWNLOADERS[granularity](
            self.cache_path, self.data_dir
        )

    def query_all(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> bool:
        self.downloader.query_all(symbols, start_date, end_date)

    def get_path(self, symbol: str) -> str:
        return self.downloader.get_path(symbol)
