import os
import re
import time
import datetime
import requests

from utils.fetch import parse_html, validate_image_url
from utils.storage import load_json, save_json, append_json_list, clear_json
from utils.hashgen import generate_item_hash
from utils.shorturl import get_short_url
from utils.discord import send_discord


# ============================
# 設定
# ============================

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

URL_EXIST = (
    "https://tsunagu.cloud/exist_products"
    "?sort=&exist_product_category_id=2"
    "&exist_product_category2_id=2"
    "&exist_product_category3_id="
    "&keyword=&max_sales_count_exist_items=1"
    "&is_selling=true&is_ai_content=0"
)

URL_AUCTION = (
    "https://tsunagu.cloud/auctions"
    "?sort=&exist_product_category_id=2"
    "&exist_product_category2_id=2"
    "&exist_product_category3_id="
    "&keyword=&is_disp_progress=1&is_ai_content=0"
)

DATA_LAST = "data/last_all.json"
DATA_SELLER = "data/seller_cache.json"
DATA_PENDING_EXIST = "data/pending_night_exist.json"
DATA_PENDING_AUCTION = "data/pending_night_auction.json"

def load_exclude_users(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip() and not line.startswith("#")}
    except FileNotFoundError:
        return set()

EXCLUDE_USERS = load_exclude_users("config/exclude_users.txt")

# ============================
# ユーティリティ
# ============================

def now():
    return datetime.datetime.now()

def is_night():
    return 2 <= now().hour < 6

def is_morning():
    return now().hour == 6 and now().minute == 0

def normalize_price(s):
    d = "".join(c for c in s if c.isdigit())
    return f"{int(d):,}円" if d else "0円"

def normalize_url(url):
    m = re.search(r"(auctions|exist_products)/(\d+)", url)
    return f"{m.group(1)}/{m.group(2)}" if m else url.split("?")[0].split("#")[0]

# ============================
# Cloudflare に強い HTML fetch
# ============================

def fetch_html(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    proxy = os.getenv("PROXY_URL")
    proxies = {"http": proxy, "https": proxy} if proxy else None

    for t in range(2):
        try:
            r = requests.get(url, headers=headers, proxies=proxies, timeout=5)
            r.raise_for_status()
            return r.text
        except Exception:
            time.sleep(1 + t)

    return ""


# ============================
# seller_id 抽出（高速・安定）
# ============================

seller_cache = {}

def fetch_seller_id(url):
    if url in seller_cache:
        return seller_cache[url]

    soup = parse_html(fetch_html(url))
    if not soup:
        seller_cache[url] = ""
        return ""

    # /users/ または /profile/ を探す
    for pat in ["/users/", "/profile/"]:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if pat in href:
                m = re.search(pat + r"([^/?#]+)", href)
                if m:
                    seller_cache[url] = m.group(1)
                    return seller_cache[url]

    seller_cache[url] = ""
    return ""


# ============================
# HTML 解析（誤検出ゼロ）
# ============================

def parse_items(soup, mode):
    items = []

    for c in soup.find_all(class_="p-product"):
        # タイトル
        t = c.find(class_="title")
        title = t.get_text(strip=True) if t else ""

        # 価格（text-danger 優先）
        price_tag = c.find("p", class_=lambda x: x and "text-danger" in x)

        if not price_tag:
            # fallback（円 or ¥ を含む数字タグ）
            for tag in c.find_all(["p", "h2", "h3"]):
                txt = tag.get_text(strip=True)
                if any(x in txt for x in ["円", "¥"]) and any(ch.isdigit() for ch in txt):
                    price_tag = tag
                    break

        price = normalize_price(price_tag.get_text(strip=True) if price_tag else "")

        # 即決価格
        buy_now = None
        h2 = c.find("h2")
        if h2 and ("即決" in h2.text):
            buy_now = normalize_price(h2.text)

        # URL
        url = c.find("a")["href"]
        if url.startswith("/"):
            url = "https://tsunagu.cloud" + url

        # サムネイル
        img_tag = c.find("img")
        thumb = img_tag["src"] if img_tag else ""

        items.append({
            "title": title,
            "price": price,
            "buy_now": buy_now,
            "thumb": thumb,
            "url": url,
            "mode": mode,
        })

    return items

# ============================
# embed 生成（短く・美しく）
# ============================

def build_embed(item):
    p = int(item["price"].replace("円", "").replace(",", ""))
    color = 0xE74C3C if p <= 5000 else 0x3498DB if p <= 9999 else 0x2ECC71
    short = get_short_url(item["url"])

    fields = [
        {"name": "URL", "value": short, "inline": False},
        {
            "name": "販売形式",
            "value": "既存販売" if item["mode"] == "exist" else "オークション",
            "inline": True,
        },
        {"name": "価格", "value": item["price"], "inline": True},
    ]

    if item["buy_now"]:
        fields.append({"name": "即決価格", "value": item["buy_now"], "inline": True})

    embed = {
        "title": item["title"][:256],
        "url": short,
        "color": color,
        "fields": fields,
    }

    img = validate_image_url(item["thumb"])
    if img:
        embed["image"] = {"url": img}

    return embed


# ============================
# メイン処理
# ============================

def main():
    global seller_cache

    # キャッシュ読み込み
    seller_cache = load_json(DATA_SELLER, default={})
    last = load_json(DATA_LAST, default={})

    # 朝6時まとめ通知
    if is_morning():
        pending = load_json(DATA_PENDING_EXIST, []) + load_json(DATA_PENDING_AUCTION, [])
        if pending:
            send_discord(WEBHOOK_URL, "🌅 深夜帯まとめ通知", pending[:10])
        clear_json(DATA_PENDING_EXIST)
        clear_json(DATA_PENDING_AUCTION)

    # HTML取得
    soup_exist = parse_html(fetch_html(URL_EXIST))
    soup_auction = parse_html(fetch_html(URL_AUCTION))

    items = []
    if soup_exist:
        items += parse_items(soup_exist, "exist")
    if soup_auction:
        items += parse_items(soup_auction, "auction")

    # 価格の安い順に並べる
    items.sort(key=lambda x: int(x["price"].replace("円", "").replace(",", "")))

    embeds = []

    # ============================
    # メインループ（重複チェック・通知判定）
    # ============================

    for item in items:
        # URL 正規化 → ハッシュ化（重複通知防止の核）
        key = normalize_url(item["url"])
        h = generate_item_hash(key)

        if h in last:
            continue

        # 価格フィルタ
        price = int(item["price"].replace("円", "").replace(",", ""))
        if price >= 15000:
            last[h] = True
            continue

        # seller_id 判定
        seller = fetch_seller_id(item["url"])
        if not seller or seller in EXCLUDE_USERS:
            last[h] = True
            continue

        # 深夜帯 → pending に保存して通知しない
        if is_night():
            path = DATA_PENDING_EXIST if item["mode"] == "exist" else DATA_PENDING_AUCTION
            append_json_list(path, item)
            last[h] = True
            continue

        # 通常通知（最大10件）
        if len(embeds) < 10:
            embeds.append(build_embed(item))

        last[h] = True

    # ============================
    # 通知送信
    # ============================

    if embeds:
        first_price = int(
            embeds[0]["fields"][2]["value"].replace("円", "").replace(",", "")
        )

        title = (
            "@everyone\n📢つなぐ　新着通知" if first_price <= 5000 else
            "🔔つなぐ　新着通知" if first_price <= 9999 else
            "📝つなぐ　新着通知"
        )

        send_discord(WEBHOOK_URL, title, embeds)

    # ============================
    # 保存（last_all / seller_cache）
    # ============================

    save_json(DATA_LAST, last)
    save_json(DATA_SELLER, seller_cache)


# ============================
# エントリーポイント
# ============================

if __name__ == "__main__":
    main()
