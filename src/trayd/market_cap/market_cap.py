from .shares_outstanding import SharesOutstanding


prog = SharesOutstanding()
prog.query_all(["NVDA"], "2000-01-01", "2010-01-01")