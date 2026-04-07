from trayd.data import MarketCapDownloader
from trayd.index import SP100, SP500
from trayd.util import get_path


START = "2000-01-01"
END = "2026-01-19"

cache_path: str = get_path("data", "cache", f"market_cap_cache_metadata.json")
data_path: str = get_path("data", "market_cap")

downloader = MarketCapDownloader(cache_path, data_path)

index = SP500()
index.load_all_npz(START)

symbols = [symbol.replace("-", ".") for symbol in index.all_symbols]
downloader.query_all(symbols, "2000-01-01", "2026-01-19")
