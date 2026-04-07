import json
import csv

import pandas as pd
import numpy as np
import os

from trayd.symbols import all_in_five_years, top_50
from trayd.util import get_path


def index_data_path(filename: str):
    return get_path("index", "data", filename)


def build_index_from_registry_csv(index_name: str):
    output_dir = get_path("index", "data")
    snapshot_csv = get_path(output_dir, f"{index_name}_registry.csv")
    out_delta_csv = get_path(output_dir, f"{index_name}_delta.csv")
    out_npz = get_path(output_dir, f"{index_name}_delta.npz")

    df = pd.read_csv(snapshot_csv, parse_dates=['date'])
    df = df.sort_values('date')

    prev_symbols: set[str] = set()
    delta_rows = []

    # ---- Pass 1: build delta CSV (event days only) ----
    for _, row in df.iterrows():
        date = pd.Timestamp(row['date']).normalize()

        symbols = set()
        if pd.notna(row['tickers']) and row['tickers']:
            symbols = {s.strip() for s in row['tickers'].split(",")}

        added = sorted(symbols - prev_symbols)
        removed = sorted(prev_symbols - symbols)

        if added or removed:
            delta_rows.append({
                "date": date,
                "added": "|".join(added),
                "removed": "|".join(removed),
            })

        # ⚠️ Always update prev_symbols
        prev_symbols = symbols

    delta_df = pd.DataFrame(delta_rows)
    delta_df.to_csv(out_delta_csv, index=False)

    # ---- Pass 2: build NPZ from deltas ----
    symbol_to_id: dict[str, int] = {}
    symbols: list[str] = []
    symbol_starts: dict[int, int] = {}

    timestamps = set()
    adds_dates, adds_symbols = [], []
    rem_dates, rem_symbols = [], []

    def get_id(sym: str) -> int:
        if sym not in symbol_to_id:
            sid = len(symbols)
            symbol_to_id[sym] = sid
            symbols.append(sym)
        return symbol_to_id[sym]

    for row in delta_rows:
        ts = row["date"].value
        timestamps.add(ts)

        if row["added"]:
            for sym in row["added"].split("|"):
                sid = get_id(sym)
                adds_dates.append(ts)
                adds_symbols.append(sid)
                symbol_starts.setdefault(sid, ts)

        if row["removed"]:
            for sym in row["removed"].split("|"):
                sid = get_id(sym)
                rem_dates.append(ts)
                rem_symbols.append(sid)

    np.savez_compressed(
        out_npz,
        timestamps=np.array(sorted(timestamps), dtype=np.int64),
        adds_dates=np.array(adds_dates, dtype=np.int64),
        adds_symbols=np.array(adds_symbols, dtype=np.int32),
        rem_dates=np.array(rem_dates, dtype=np.int64),
        rem_symbols=np.array(rem_symbols, dtype=np.int32),
        symbol_list=np.array(symbols, dtype=object),
        symbol_start_dates=np.array(
            [symbol_starts.get(i, -1) for i in range(len(symbols))],
            dtype=np.int64
        )
    )

    print("Build complete (event days only):")
    print(f"  Delta CSV → {out_delta_csv}")
    print(f"  NPZ       → {out_npz}")


symbols = all_in_five_years


def build_static_index_npz(
    index_name: str,
    symbols: list[str],
    start_date: str,
):
    output_dir = get_path("index", "data")
    os.makedirs(output_dir, exist_ok=True)

    out_npz = get_path(output_dir, f"{index_name}_delta.npz")

    start_ts = pd.Timestamp(start_date).normalize().value

    # Symbol ID mapping
    symbol_list = list(symbols)
    symbol_to_id = {s: i for i, s in enumerate(symbol_list)}

    # One event date
    timestamps = np.array([start_ts], dtype=np.int64)

    # All symbols added on start date
    adds_dates = np.full(len(symbol_list), start_ts, dtype=np.int64)
    adds_symbols = np.arange(len(symbol_list), dtype=np.int32)

    # No removals
    rem_dates = np.array([], dtype=np.int64)
    rem_symbols = np.array([], dtype=np.int32)

    # All symbols start on start_date
    symbol_start_dates = np.full(len(symbol_list), start_ts, dtype=np.int64)

    np.savez_compressed(
        out_npz,
        timestamps=timestamps,
        adds_dates=adds_dates,
        adds_symbols=adds_symbols,
        rem_dates=rem_dates,
        rem_symbols=rem_symbols,
        symbol_list=np.array(symbol_list, dtype=object),
        symbol_start_dates=symbol_start_dates,
    )

    print("Static index NPZ created:")
    print(f"  NPZ → {out_npz}")
    print(f"  Symbols: {len(symbol_list)}")
    print(f"  Start date: {start_date}")



INPUT_JSON = "input.json"
OUTPUT_CSV = "output.csv"


def convert_old_to_csv(index: str):
    input_json = index_data_path(f"{index}.json")
    output_csv = index_data_path(f"{index}_registry.csv")

    with open(input_json, "r") as f:
        data: dict = json.load(f)
    
    data.pop("start", None)
    data = {timestamp: symbols for timestamp, symbols in data.items() if symbols != []}

    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "tickers"])

        for date, tickers in sorted(data.items()):
            writer.writerow([
                date,
                ",".join(tickers)
            ])

    print(f"Wrote {output_csv}")


def top_n(index: str, n: int):
    top_n_data = {}
    with open(index_data_path(f"{index}.json"), 'r') as fp:
        data = json.load(fp)

    for timestamp, symbols in data.items():
        top_n_data[timestamp] = symbols[:n]

    with open(index_data_path(f"top_{n}.json"), 'w') as fp:
        json.dump(top_n_data, fp)
 

def convert_and_build(index: str):
    convert_old_to_csv(index)
    build_index_from_registry_csv(index)

convert_and_build("top50_5yrs")
# top_n("top50_5yrs", 25)
# build_static_index_npz("JustSpy", ["SPY"], "1970-12-25")
# convert_old_to_csv("top_25")