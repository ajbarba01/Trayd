import os

from dotenv import load_dotenv

if __name__ == "__config__":
    load_dotenv()

    POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
    FMP_API_KEY = os.getenv("FMP_API_KEY")
