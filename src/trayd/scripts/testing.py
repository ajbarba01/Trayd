from sec_cik_mapper import StockMapper

mapper = StockMapper()
ticker_to_cik = mapper.ticker_to_cik
print(f"Loaded {len(ticker_to_cik)} tickers.")