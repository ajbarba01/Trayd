import json
from enum import StrEnum


class Variable(StrEnum):
    MACD_BUYING = "MACD_BUYING"
    MACD_SELLING = "MACD_SELLING"
    MACD_SOLD_OPEN = "MACD_SOLD_OPEN"
    MACD_BOUGHT_CLOSE = "MACD_BOUGHT_CLOSE"
    MACD_CLOSED_TODAY = "MACD_CLOSED_TODAY"


class NonVolatile:

    data_path = "non_volatile.json"
    data = {}

    @staticmethod
    def load():
        with open(NonVolatile.data_path, 'r') as fp:
            NonVolatile.data = json.load(fp)


    @staticmethod
    def save():
        with open(NonVolatile.data_path, 'w') as fp:
            json.dump(NonVolatile.data, fp, indent=4)

    
    @staticmethod
    def get(variable: Variable):
        return NonVolatile.data.get(variable)
    

    @staticmethod
    def store(variable: Variable, value: any):
        NonVolatile.data[variable] = value