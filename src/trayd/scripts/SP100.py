import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import json
import os

WAYBACK_CDX_URL = "https://web.archive.org/cdx/search/cdx"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
OUTPUT_FILE = "historical_sp100.json"

def get_wayback_snapshots(url, start_year=2000, end_year=2025):
    params = {
        "url": url,
        "output": "json",
        "from": start_year,
        "to": end_year,
        "filter": "statuscode:200",
        "collapse": "timestamp"
    }
    response = requests.get(WAYBACK_CDX_URL, params=params, headers=HEADERS, timeout=10)
    response.raise_for_status()
    data = response.json()
    return [entry[1] for entry in data[1:]]  # skip header

def scrape_sp100_from_snapshot(snapshot_timestamp, max_retries=3):
    snapshot_url = f"https://web.archive.org/web/{snapshot_timestamp}/https://en.wikipedia.org/wiki/S%26P_100"
    for attempt in range(max_retries):
        try:
            response = requests.get(snapshot_url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            table = soup.find("table", {"class": "wikitable sortable"})
            tickers = []
            if table:
                rows = table.find_all("tr")[1:]  # skip header
                for row in rows:
                    cells = row.find_all("td")
                    if cells:
                        ticker = cells[0].text.strip()
                        tickers.append(ticker)
            return tickers
        except (requests.RequestException, Exception) as e:
            print(f"Attempt {attempt+1} failed for {snapshot_timestamp}: {e}")
            time.sleep(2)
    return []

def save_data(historical_data, filename=OUTPUT_FILE):
    """
    Sort data by timestamp before saving
    """
    sorted_items = sorted(
        historical_data.items(), 
        key=lambda x: datetime.strptime(x[0], "%Y-%m-%d")
    )
    sorted_data = {k: v for k, v in sorted_items}
    
    with open(filename, "w") as f:
        json.dump(sorted_data, f, indent=2)
    print(f"Saved {len(sorted_data)} snapshots to {filename}")

def load_existing_data(filename=OUTPUT_FILE):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}

def get_historical_sp100(start_year=2010, end_year=2025, delay=1.0):
    url = "https://en.wikipedia.org/wiki/S%26P_100"
    historical_data = load_existing_data()
    snapshots = get_wayback_snapshots(url, start_year, end_year)

    # Convert existing keys to a set for fast checking
    existing_dates = set(historical_data.keys())

    try:
        for ts in snapshots:
            timestamp_str = datetime.strptime(ts, "%Y%m%d%H%M%S").strftime("%Y-%m-%d")
            if timestamp_str in existing_dates:
                continue  # skip already scraped snapshots

            tickers = scrape_sp100_from_snapshot(ts)
            if tickers:
                historical_data[timestamp_str] = tickers
                print(f"Scraped {len(tickers)} tickers for {timestamp_str}")

            time.sleep(delay)

    except KeyboardInterrupt:
        print("KeyboardInterrupt detected! Saving progress...")

    save_data(historical_data)
    return historical_data

if __name__ == "__main__":
    historical_sp100 = get_historical_sp100(2000, 2026)
    # print(historical_sp100)
