from trayd.data import MarketCapDownloader, ParquetLoader
from trayd.index import SP100, SP500
from trayd.util import get_path

import pandas as pd

import os
import json

START = "2010-01-01"
END = "2026-01-19"
N = 50

index = SP500()
index.load_all_npz(START)

current = pd.Timestamp(START)
end = pd.Timestamp(END)

cache_path: str = get_path("data", "cache", f"market_cap_cache_metadata.json")
data_path: str = get_path("data", "market_cap")

loader = ParquetLoader(cache_path, data_path)
dated_data = loader.load_all_dated(index.all_symbols)

# print(dated_data["MSFT"])

top_n = {}
while current < end:
    current_date = current.date()
    current_symbols = index.current_symbols
    caps = {}
    for symbol in current_symbols:
        if symbol in dated_data:        
            entry = dated_data[symbol]
            if current in entry:
                cap = entry[current]["marketCap"]
                caps[symbol] = cap

    # print(caps)
    keys = sorted(caps, key=caps.get, reverse=True)[:N]
    if keys:
        top_n[current_date] = keys
    
    current = (current + pd.Timedelta(days=1)).normalize()
    index.update_to(current)


top_n_json = {
    date.isoformat(): symbols
    for date, symbols in top_n.items()
}

# Output path
data_path = get_path("index", "data")
output_path = get_path(data_path, f"SP{N}.json")

# Save as formatted JSON
with open(output_path, "w") as f:
    json.dump(top_n_json, f, indent=4)

print(f"Saved top {N} market cap symbols to {output_path}")