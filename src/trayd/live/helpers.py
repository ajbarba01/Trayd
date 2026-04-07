from alpaca.trading.enums import OrderStatus

import math
import time

def format_USD(amount: float) -> str:
    return f"${amount:,.2f}"


def bad_order_status(status: OrderStatus):
    return status == OrderStatus.EXPIRED or status == OrderStatus.REJECTED or OrderStatus == OrderStatus.CANCELED

    
def floor_cent(amount: float):
    return math.floor(amount * 100) / 100

def ceil_cent(amount: float):
    return math.ceil(amount * 100) / 100


def is_within_seconds(time_s: float, seconds: float) -> bool:
    return time_s > time.time() - seconds
