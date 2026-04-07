from .backtest import Backtest

from trayd.algorithms import *

def main():
    backtest = Backtest("2020-12-10", "2025-12-19", SellOpen(), 10_000, using_intraday=True, leverage=2.0, max_exposure=1.0)
    backtest.run()


if __name__ == "__main__":
    main()