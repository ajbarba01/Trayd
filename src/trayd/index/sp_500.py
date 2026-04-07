from .index import Index


class SP500(Index):
    def __init__(self):
        super().__init__("SP500")
