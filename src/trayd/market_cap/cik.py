import pandas as pd

cik_df = pd.read_csv("cik_ticker.csv")
symbol = "AAPL"
cik = cik_df.loc[cik_df["Ticker"] == symbol, "CIK"].values[0]
cik = str(cik).zfill(10)
