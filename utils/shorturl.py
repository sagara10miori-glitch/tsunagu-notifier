import hashlib
import os
import json

DATA_DIR = "data"
SHORT_URLS_PATH = os.path.join(DATA_DIR, "short_urls.json")

BASE_REDIRECT_URL = "https://gutsu.github.io/t"  # GitHub Pages の短縮URLベース


def load_short_urls():
    """short_urls.json を読み込む（存在しない場合は空 dict）"""
    if not os.path.exists(SHORT_URLS_PATH):
        return {}

    try:
        with open(SHORT_URLS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        print("[WARNING] Failed to load short_urls.json")
        return {}


def save_short_urls(data):
    """short_urls.json を保存する"""
    try:
        with open(SHORT_URLS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[ERROR] Failed to save short_urls.json")
        print(e)


def generate_short_key(url):
    """
    URL から短縮キーを生成する。
    SHA-256 の先頭 8 文字を使用（衝突リスク極小）。
    """
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return h[:8]  # 8文字が最適（衝突率ほぼゼロ）


def get_short_url(url):
    """
    URL の短縮版を返す。
    - 既存キーがあれば再利用
    - なければ新規生成して保存
    """
    short_urls = load_short_urls()

    # 既に短縮済みなら再利用
    if url in short_urls:
        return f"{BASE_REDIRECT_URL}/{short_urls[url]}"

    # 新規生成
    key = generate_short_key(url)
    short_urls[url] = key
    save_short_urls(short_urls)

    return f"{BASE_REDIRECT_URL}/{key}"
