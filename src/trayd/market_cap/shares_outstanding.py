import time
import json
import os
import pandas as pd
from .sec_scraper import SECScraper

from trayd.util import get_path


class SharesOutstanding:
    CACHE_FILE = get_path("market_cap", "shares_outstanding_cache.json")
    TEMP_CACHE_FILE = get_path("market_cap", "shares_outstanding_cache.tmp.json")

    def __init__(self):
        self.start_time = time.time()
        self.scraper = SECScraper(min_delay=0.05)
        self.shares_outstanding_cache = {}
        self.load_cache()

    # ------------------ CACHE HANDLING ------------------

    def load_cache(self):
        """Load existing shares outstanding cache from JSON."""
        if os.path.exists(self.CACHE_FILE):
            with open(self.CACHE_FILE, "r") as f:
                raw = json.load(f)
                # Convert timestamps to pd.Timestamp
                for symbol, value in raw.items():
                    start_ts = pd.Timestamp(value["range"][0])
                    end_ts = pd.Timestamp(value["range"][1])
                    data = {pd.Timestamp(k): v for k, v in value["data"].items()}
                    self.shares_outstanding_cache[symbol] = {"range": (start_ts, end_ts), "data": data}
            print(f"Loaded cache for {len(self.shares_outstanding_cache)} tickers.")
        else:
            self.shares_outstanding_cache = {}
            print("No cache file found. Starting fresh.")

    def save_cache(self):
        """Save cache safely via temporary file to avoid corruption."""
        raw = {}
        for symbol, value in self.shares_outstanding_cache.items():
            start_ts = value["range"][0].isoformat()
            end_ts = value["range"][1].isoformat()
            data = {k.isoformat(): v for k, v in value["data"].items()}
            raw[symbol] = {"range": (start_ts, end_ts), "data": data}

        with open(self.TEMP_CACHE_FILE, "w") as f:
            json.dump(raw, f, indent=4)
        os.replace(self.TEMP_CACHE_FILE, self.CACHE_FILE)
        print(f"Saved cache for {len(self.shares_outstanding_cache)} tickers.")

    # ------------------ QUERY LOGIC ------------------
    def query_all(self, symbols: list[str], start_date="2020-01-01", end_date="2025-12-31"):
        start_date = pd.Timestamp(start_date)
        end_date = pd.Timestamp(end_date)

        for symbol in symbols:
            cached = self.shares_outstanding_cache.get(symbol)

            new_data = {}
            final_start = start_date
            final_end = end_date

            # ---------- NO CACHE ----------
            if not cached:
                shares = self.scraper.get_shares_in_date_range(
                    symbol=symbol,
                    filing_type="10-Q",
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d")
                )
                # Convert keys to pd.Timestamp
                new_data.update({pd.Timestamp(k): v for k, v in shares.items()})

            # ---------- CACHE EXISTS ----------
            else:
                cached_start, cached_end = cached["range"]
                cached_data = cached["data"]

                # LEFT GAP
                if start_date < cached_start:
                    left_end = cached_start - pd.Timedelta(days=1)
                    shares = self.scraper.get_shares_in_date_range(
                        symbol=symbol,
                        filing_type="10-Q",
                        start_date=start_date.strftime("%Y-%m-%d"),
                        end_date=left_end.strftime("%Y-%m-%d")
                    )
                    new_data.update({pd.Timestamp(k): v for k, v in shares.items()})

                # RIGHT GAP
                if end_date > cached_end:
                    right_start = cached_end + pd.Timedelta(days=1)
                    shares = self.scraper.get_shares_in_date_range(
                        symbol=symbol,
                        filing_type="10-Q",
                        start_date=right_start.strftime("%Y-%m-%d"),
                        end_date=end_date.strftime("%Y-%m-%d")
                    )
                    new_data.update({pd.Timestamp(k): v for k, v in shares.items()})

                # Merge with cached
                new_data = {**cached_data, **new_data}
                final_start = min(start_date, cached_start)
                final_end = max(end_date, cached_end)

                # Fully covered → no requests
                if not new_data:
                    print(f"{symbol} fully cached. Skipping.")
                    continue

            # ---------- UPDATE CACHE ----------
            self.shares_outstanding_cache[symbol] = {
                "range": (final_start, final_end),
                "data": new_data
            }

            for dt, shares in sorted(new_data.items()):
                print(symbol, dt.strftime("%Y-%m-%d"), shares)

        self.save_cache()
        print("ELAPSED:", time.time() - self.start_time)
