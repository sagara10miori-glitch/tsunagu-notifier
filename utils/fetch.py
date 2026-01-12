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

def validate_image_url(url):
    # 空文字は NG
    if not url or url.strip() == "":
        return None

    # 相対URLなら絶対URLに変換
    if url.startswith("/"):
        url = "https://tsunagu.cloud" + url

    # HEAD リクエストで存在確認
    try:
        r = requests.head(url, timeout=5)
        if r.status_code == 200:
            return url
    except:
        pass

    return None
