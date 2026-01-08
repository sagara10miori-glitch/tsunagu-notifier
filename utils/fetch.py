import requests
from bs4 import BeautifulSoup
import hashlib
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

TIMEOUT = 10
RETRY = 3


def fetch_html(url):
    """
    HTML を取得する（リトライ付き）。
    失敗した場合は None を返す。
    """
    for i in range(RETRY):
        try:
            res = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if res.status_code == 200:
                return res.text
            else:
                print(f"[WARNING] HTTP {res.status_code} → {url}")
        except Exception as e:
            print(f"[WARNING] Fetch failed ({i+1}/{RETRY}) → {url}")
            print(e)
            time.sleep(1)

    print(f"[ERROR] Failed to fetch HTML → {url}")
    return None


def parse_html(html):
    """
    BeautifulSoup で HTML を解析して返す。
    """
    if not html:
        return None
    return BeautifulSoup(html, "html.parser")


def get_html_hash(html):
    """
    HTML の構造変化を検知するためのハッシュを生成する。
    余計な空白や改行を除去してから SHA-256 を取る。
    """
    if not html:
        return None

    normalized = " ".join(html.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def detect_structure_change(old_hash, new_hash, label="HTML"):
    """
    HTML の構造変化を検知する。
    ハッシュが変わっていたら警告を出す。
    """
    if not old_hash or not new_hash:
        return

    if old_hash != new_hash:
        print(f"[WARNING] {label} structure changed!")
