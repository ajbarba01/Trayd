import os
import json

from trayd.util import get_path


class Config:
    CONFIG_PATH = get_path("config", "config.json")
    API_KEY = ""
    SECRET_KEY = ""
    DATA_API_KEY = ""
    DATA_SECRET_KEY = ""
    ET = None
    tick_rate = 5.0
    portfolio_refresh_rate = 1.0
    cancel_defer_duration = 4.0
    validation_rate = 5.0
    secondary_validation_rate = 10.0
    ux_draw_rate = 0.5
    ux_render_framerate = 60.0
    extended_check_rate = 5.0
    extended_tick_rate = 15.0
    main_loop_rate = 0.001
    can_buy = False
    can_sell = False
    can_run = False
    extended_hours = False


    @staticmethod
    def set_et(et):
        Config.ET = et

    @staticmethod 
    def load(algorithm):
        with open(Config.CONFIG_PATH, 'r') as fp:
            data = json.load(fp)
        
        account_data = data["accounts"][algorithm.account_name]
        Config.extended_hours = algorithm.extended_hours
        Config.API_KEY = account_data["API_KEY"]
        Config.SECRET_KEY = account_data["SECRET_KEY"]
        Config.DATA_API_KEY = data["data_account"]["API_KEY"]
        Config.DATA_SECRET_KEY = data["data_account"]["SECRET_KEY"]
        Config.can_buy = data["can_buy"]
        Config.can_sell = data["can_sell"]

    @staticmethod
    def save():
        with open(Config.CONFIG_PATH, 'r') as fp:
            data = json.load(fp)

        data["can_buy"] = Config.can_buy
        data["can_sell"] = Config.can_sell

        with open(Config.CONFIG_PATH, 'w') as fp:
            json.dump(data, fp, indent=4)

