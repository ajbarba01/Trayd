from dataclasses import dataclass

@dataclass
class LocalPosition:
    symbol: str
    qty: float = 0.0
    avg_entry_price: float = 0.0
