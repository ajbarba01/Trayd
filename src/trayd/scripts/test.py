from polygon import RESTClient
from datetime import datetime, timedelta
from trayd.config import POLYGON_API_KEY

# ============ CONFIGURATION ============
API_KEY = POLYGON_API_KEY  # or use os.environ
SYMBOL = "NVDA"
MULTIPLIER = 5  # 5‑minute bars
TIMESPAN = "minute"
DAYS = 100  # how many days back
# =======================================

# Create REST client
client = RESTClient(api_key=API_KEY)

# Calculate date range
end_dt = datetime.utcnow()
start_dt = end_dt - timedelta(days=DAYS)

# Format dates for Polygon
from_str = start_dt.strftime("%Y-%m-%d")
to_str = end_dt.strftime("%Y-%m-%d")

# Now fetch and count
all_bars = []

# Use list_aggs to iterate across pages
for bar in client.list_aggs(
    SYMBOL,
    MULTIPLIER,
    TIMESPAN,
    from_str,
    to_str,
    limit=50000,  # max possible per request
):
    all_bars.append(bar)

print(f"Retrieved {len(all_bars)} five‑minute bars for {SYMBOL}")
# print(all_bars)
