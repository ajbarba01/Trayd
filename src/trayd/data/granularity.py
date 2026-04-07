import pandas as pd
from enum import StrEnum


class Granularity(StrEnum):
    DAY = "1d"
    INTRADAY = "5m"
