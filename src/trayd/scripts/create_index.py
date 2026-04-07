
import pandas as pd
import os
from trayd.symbols import top_50, all_in_five_years
from trayd.util import get_path

symbols = all_in_five_years


# Create DataFrame
df = pd.DataFrame({
    "symbol": symbols,
    "start_date": pd.to_datetime("2020-12-25"),
    "end_date": pd.to_datetime("2025-12-25")
})

# Save to CSV
name = "all_5yrs"
file = "index_" + name + ".csv"
path = get_path("index", "data", file)
df.to_csv(path, index=False)