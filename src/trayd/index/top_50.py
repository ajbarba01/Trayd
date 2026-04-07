from .index import Index

from trayd.symbols import top_50, all_in_five_years


class Top50(Index):
    def __init__(self):
        super().__init__("top50_5yrs")
        # super().__init__("top50_5yrs")
        # super().__init__("5yrs")
