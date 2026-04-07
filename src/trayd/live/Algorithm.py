from live.Portfolio import Portfolio
from live.LiveData import LiveData, LocalBar
from live.Index import Index
from live.Logger import Logger

from trayd.util import get_path

from helpers import floor_cent, ceil_cent, format_USD

import os


class Algorithm:
    def __init__(self, name: str, account_name: str, index: Index, portfolio: Portfolio, live_data: LiveData):
        self.index = index
        self.portfolio = portfolio
        self.live_data = live_data
        self.name = name
        self.account_name = account_name
        self.tick_rate = 60.0
        self.extended_tick_rate = 60.0
        self.should_cancel = False
        self.cancel_defer = 59.0
        self.extended_cancel_defer = 59.0
        self.extended_hours = True

        self.portfolio_max_size = 10

        self.algorithm_dir = "algorithm"


    def initialize(self):
        pass


    def get_path(self) -> str:
        return get_path(self.algorithm_dir, self.name)


    def exit(self):
        pass



    def algorithm_tick(self):
        pass


    def extended_algorithm_tick(self):
        self.algorithm_tick()


    def on_extended_bar_data(self, bar: LocalBar):
        pass


    def on_bar_data(self, bar: LocalBar):
        pass
    

    def company_per(self, portfolio_max_size: float=None) -> float:
        if not portfolio_max_size:
            portfolio_max_size = self.portfolio_max_size

        return self.portfolio.portfolio_value / portfolio_max_size
    

    def closest_share_amount(self, symbol: str, max_price: float=None, max_size: float=None):
        if not max_price:
            max_price = self.company_per(max_size)
        
        price = self.live_data.get_high(symbol)
        return int(max_price // price)
    
    

