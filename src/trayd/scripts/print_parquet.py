import pandas as pd
import sys

def print_parquet_preview(path: str, n: int = 5):
    # Load the file
    df = pd.read_parquet(path)

    print(f"\n===== {path} =====\n")
    print(f"Number of rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    print("\nData types:")
    print(df.dtypes)

    print(f"\nFirst {n} rows:")
    print(df.head(n))

    print(f"\nLast {n} rows:")
    print(df.tail(n))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py print_parquet_preview.py file.parquet [num_rows]")
        sys.exit(1)

    path = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    print_parquet_preview(path, n)
