import os
import json
import pandas as pd
from pathlib import Path

# ---------------- CONFIG ----------------
INPUT_DIR = Path("json_data")  # directory containing *.json
OUTPUT_DIR = Path("parquet_data")  # output directory
SYMBOLS = {"AAPL", "MSFT", "GOOG"}  # symbols to convert
# ---------------------------------------

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

for file in INPUT_DIR.glob("*.json"):
    symbol = file.stem

    if symbol not in SYMBOLS:
        continue

    with open(file, "r") as f:
        raw = json.load(f)

    if symbol not in raw:
        raise ValueError(f"{symbol} key not found in {file.name}")

    data = raw[symbol]

    # Build DataFrame
    df = pd.DataFrame.from_dict(data, orient="index", columns=COLUMNS)

    # Convert index to datetime (keeps minute resolution)
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"

    # Sort by time
    df.sort_index(inplace=True)

    # Add Adj Close (same as Close)
    df["Adj Close"] = df["Close"]

    # Reorder columns
    df = df[["Open", "High", "Low", "Close", "Adj Close", "Volume"]]

    # Enforce dtypes
    df = df.astype(
        {
            "Open": "float64",
            "High": "float64",
            "Low": "float64",
            "Close": "float64",
            "Adj Close": "float64",
            "Volume": "int64",
        }
    )

    # Write parquet
    out_path = OUTPUT_DIR / f"{symbol}.parquet"
    df.to_parquet(out_path, engine="pyarrow")

    print(f"✔ Converted {symbol} → {out_path}")
