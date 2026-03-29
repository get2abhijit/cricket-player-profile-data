"""
Test the proper ESPN URL format by checking actual player profile slug behavior.
"""
import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Test with the example the user gave: Alister Gajic (ID 1323426)
# URL: https://www.espncricinfo.com/cricketers/alister-gajic-1323426

test_urls = [
    "https://www.espncricinfo.com/cricketers/alister-gajic-1323426",
    "https://www.espncricinfo.com/cricketers/_/id/1323426",
]

for url in test_urls:
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"{r.status_code} {url[:70]}")
        # Check if there is a canonical link showing the proper slug
        soup = BeautifulSoup(r.text, "html.parser")
        canonical = soup.find("link", rel="canonical")
        if canonical:
            print(f"  Canonical: {canonical.get('href')}")
    except Exception as e:
        print(f"ERROR {url}: {e}")
