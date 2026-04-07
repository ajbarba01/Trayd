from alpaca.data.models import Bar

from live.Logger import Logger

from datetime import datetime, timedelta


class Indicator:
    def __init__(self, symbol: str, minute_granularity: int):
        self.symbol = symbol
        self.minute_granularity = minute_granularity
        self.last_timestamp = None
        self.warmup_time = 0


    def is_ready(self) -> bool:
        return False


    def update(self, timestamp: datetime, value: any):
        timestamp = timestamp.replace(second=0, microsecond=0)
        if self.last_timestamp is None:
            # first update
            self.last_timestamp = timestamp
            self.on_update(value)
            return

        delta = timestamp - self.last_timestamp  # timedelta
        expected_delta =  timedelta(minutes=self.minute_granularity)
        if delta >= expected_delta:
            if delta > expected_delta:
                pass
                # Logger.log_message(f"Missed timestamp indicator for {self.symbol}, {self.last_timestamp} vs. {timestamp}")
            # more than 5 minutes since last update
            self.last_timestamp = timestamp
            self.on_update(value)

        else:
            pass
            # Logger.log_message(f"Invalid timestamp indicator for {self.symbol}, {self.last_timestamp} vs. {timestamp}")


    def on_update(self, value: any):
        pass

    
    def get(self):
        return None if not self.is_ready() else self