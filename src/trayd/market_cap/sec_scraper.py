import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
from threading import Lock, Thread
from sec_cik_mapper import StockMapper
from urllib.parse import urljoin

# Regex patterns for older filings
SHARES_PATTERNS = [
    r"([\d,]+)\s+shares of common stock were issued and outstanding",
    r"([\d,]+)\s+shares of\s+Common Stock Issued and Outstanding",
    r"([\d,]+)\s+and\s+([\d,]+)\s+shares issued and outstanding, respectively",
    r"([\d,]+)\s+shares authorized; ([\d,]+)\s+shares issued and outstanding",
    r"([\d,]+)\s+shares issued and outstanding",
]

UNIT_MULTIPLIERS = {
    "million": 1_000_000,
    "millions": 1_000_000,
    "thousand": 1_000,
    "thousands": 1_000,
    "billion": 1_000_000_000,
    "billions": 1_000_000_000,
}

class SECScraper:
    def __init__(self, user_agent: str = "Backtester alex@Barba.org", min_delay: float = 0.1):
        """
        min_delay: minimum delay (in seconds) between SEC requests
        """
        self.headers = {"User-Agent": user_agent}
        self.min_delay = min_delay
        self._last_request_time = 0
        self._lock = Lock()
        self.mapper = StockMapper()
        self.ticker_to_cik = self.mapper.ticker_to_cik  # dict: {ticker: cik}

        
    def get_cik(self, symbol: str) -> str | None:
        return self.ticker_to_cik.get(symbol.upper())
    

    def _rate_limited_get(self, url: str) -> requests.Response:
        """Thread-safe requests.get with minimum delay between calls"""
        with self._lock:
            now = time.time()
            wait = self.min_delay - (now - self._last_request_time)
            if wait > 0:
                time.sleep(wait)
            response = requests.get(url, headers=self.headers)
            self._last_request_time = time.time()
        return response

    def normalize_sec_url(self, url: str) -> str:
        if "/ix?doc=" in url:
            url = url.split("/ix?doc=")[-1]
            url = "https://www.sec.gov" + url
        return url

    def get_filing_urls(self, cik: str, filing_type: str = "10-Q",
                        start_date: str = "2000-01-01", end_date: str = "2030-12-31", count: int = 100):
        """Returns a dict {filing_date: filing_url} within the date range"""
        search_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={filing_type}&owner=exclude&count={count}"
        response = self._rate_limited_get(search_url)
        if response.status_code != 200:
            print(f"Failed to fetch EDGAR page for CIK {cik}")
            return {}

        soup = BeautifulSoup(response.text, "html.parser")
        tables = soup.find_all("table")
        if len(tables) < 3:
            return {}

        filing_table = tables[2]
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        urls = {}
        for row in filing_table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            filing_date = cells[3].get_text(strip=True)
            filing_dt = datetime.strptime(filing_date, "%Y-%m-%d")
            if start_dt <= filing_dt <= end_dt:
                link_tag = cells[1].find("a")
                if link_tag and "href" in link_tag.attrs:
                    filing_url = "https://www.sec.gov" + link_tag['href']
                    urls[filing_dt] = filing_url
        return urls
    
    def get_complete_submission_txt(self, filing_url: str) -> str | None:
        filing_url = self.normalize_sec_url(filing_url)
        response = self._rate_limited_get(filing_url)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", class_="tableFile")
        if not table:
            return None

        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue

            # Look for the correct row by label text
            description_text = " ".join(c.get_text(strip=True) for c in cells).lower()
            if "complete submission text file" not in description_text:
                continue
                
            # Find the first <a> tag inside this row
            link_tag = row.find("a", href=True)
            if link_tag:
                return urljoin("https://www.sec.gov", link_tag["href"])

        return None

    def extract_shares_from_ixbrl(self, url: str) -> int | None:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        url = self.normalize_sec_url(url)
        response = self._rate_limited_get(url)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        tag = soup.find(
            "ix:nonfraction",
            attrs={"name": "dei:EntityCommonStockSharesOutstanding"}
        )

        if not tag:
            return None

        text = tag.get_text(strip=True).replace(",", "")
        try:
            value = float(text)
        except ValueError:
            return None

        # Determine the unit multiplier
        multiplier = 1

        # First, look for scale
        scale = tag.get("scale")
        if scale:
            # Only apply scale if < 12 (to avoid crazy overinflation)
            try:
                scale_int = int(scale)
                if scale_int < 12:
                    multiplier = 10 ** scale_int
            except ValueError:
                pass

        # Then check human-readable text
        next_text = tag.next_sibling
        if next_text:
            next_text = str(next_text).lower()
            if "billion" in next_text:
                multiplier = 1_000_000_000
            elif "million" in next_text:
                multiplier = 1_000_000

        value *= multiplier
        return int(round(value))

    

    def extract_shares_from_text(self, url: str) -> int | None:
        response = self._rate_limited_get(url)
        if response.status_code != 200:
            return None

        text = response.text.lower()

        for pattern in SHARES_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue

            number_str = match.groups()[-1].replace(",", "")
            value = int(number_str)

            # Look nearby for units (±200 chars window)
            start, end = match.span()
            window = text[max(0, start - 200): min(len(text), end + 200)]
            print(window)

            multiplier = 1
            for unit, mult in UNIT_MULTIPLIERS.items():
                if unit in window:
                    multiplier = mult
                    break

            return value * multiplier

        return None

    def get_shares_outstanding(self, filing_url: str) -> int:
        """
        Attempts to get shares from iXBRL, then from plain text.
        """
        txt_url = self.get_complete_submission_txt(filing_url)
        if txt_url:
            shares = self.extract_shares_from_ixbrl(txt_url)
            if shares is not None:
                return shares
            shares = self.extract_shares_from_text(txt_url)
            if shares is not None:
                return shares
            
        return None

    def get_shares_in_date_range(self, symbol: str, filing_type: str = "10-Q",
                                start_date: str = "2000-01-01", end_date: str = "2030-12-31") -> dict:
        """
        Fetch filings in the date range, extract shares outstanding.
        Returns dict: {"YYYY-MM-DD": shares}.
        """
        cik = self.get_cik(symbol)
        print(cik)
        if not cik:
            print(f"Skipping {symbol}, no CIK available.")
            return {}

        filings = self.get_filing_urls(cik, filing_type, start_date, end_date)
        # print(filings)
        if not filings:
            return {}

        results = {}
        threads = []
        success = {"ok": True}

        def worker(filing_dt, filing_url):
            try:
                shares = self.get_shares_outstanding(filing_url)
                if shares is not None:
                    # Convert to clean string date
                    results[filing_dt.strftime("%Y-%m-%d")] = shares
                else:
                    print(shares)
            except Exception:
                success["ok"] = False

        for filing_dt, filing_url in filings.items():
            t = Thread(target=worker, args=(filing_dt, filing_url))
            t.start()
            threads.append(t)
            time.sleep(self.min_delay)  # keep your rate limiting

        for t in threads:
            t.join()

        if not success["ok"]:
            print("FAILED")
            exit()

        # Sort by date string
        results = dict(sorted(results.items(), reverse=True))
        return results
