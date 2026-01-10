import requests
from bs4 import BeautifulSoup

def fetch_html(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.text

def parse_html(html):
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return None
