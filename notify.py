import os
import datetime
import re
import time
import requests

from utils.safety import safe_run
from utils.fetch import parse_html, validate_image_url
from utils.hashgen import generate_item_hash
from utils.shorturl import get_short_url
from utils.storage import load_json, save_json, append_json_list, clear_json
from utils.discord import send_discord


# -----------------------------
# 高速 fetch_html（UA + timeout + retry + プロキシ対応）
# -----------------------------
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

    proxy_url = os.getenv("PROXY_URL")
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    for attempt in range(2):
        try:
            res = requests.get(url, headers=headers, proxies=proxies, timeout=5)
            res.raise_for_status()
            return res.text
        except Exception:
            time.sleep(1 + attempt)
            continue

    return ""


# -----------------------------
# 設定
# -----------------------------
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

DATA_LAST_ALL = "data/last_all.json"
DATA_PENDING_EXIST = "data/pending_night_exist.json"
DATA_PENDING_AUCTION = "data/pending_night_auction.json"
DATA_SELLER_CACHE = "data/seller_cache.json"


# -----------------------------
# 除外ユーザー
# -----------------------------
def load_exclude_users(path: str) -> set:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip() and not line.startswith("#")}
    except FileNotFoundError:
        return set()


EXCLUDE_USERS = load_exclude_users("config/exclude_users.txt")


# -----------------------------
# seller_id キャッシュ
# -----------------------------
seller_cache = {}


# -----------------------------
# URL 正規化（再通知防止の最重要ポイント）
# -----------------------------
def normalize_item_url(url: str) -> str:
    m = re.search(r"(auctions|exist_products)/(\d+)", url)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return url.split("?")[0].split("#")[0]


# -----------------------------
# ユーティリティ
# -----------------------------
def is_night() -> bool:
    return 2 <= datetime.datetime.now().hour < 6


def is_morning_summary() -> bool:
    now = datetime.datetime.now()
    return now.hour == 6 and now.minute == 0


def normalize_price(price_str: str) -> str:
    if not price_str:
        return "0円"
    digits = "".join(c for c in price_str if c.isdigit())
    if digits == "":
        return "0円"
    return f"{int(digits):,}円"


# -----------------------------
# seller_id 取得（完全対応版）
# -----------------------------
def fetch_seller_id_from_detail(url):
    if url in seller_cache:
        return seller_cache[url]

    html = fetch_html(url)
    soup = parse_html(html)
    if not soup:
        seller_cache[url] = ""
        return ""

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/users/" in href:
            m = re.search(r"/users/([^/?#]+)", href)
            if m:
                seller_id = m.group(1).strip()
                seller_cache[url] = seller_id
                return seller_id

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/profile/" in href:
            m = re.search(r"/profile/([^/?#]+)", href)
            if m:
                seller_id = m.group(1).strip()
                seller_cache[url] = seller_id
                return seller_id

    seller_cache[url] = ""
    return ""


# -----------------------------
# 通知文言
# -----------------------------
def get_notification_title(price_num):
    if price_num <= 5000:
        return "@everyone\n📢つなぐ　新着通知"
    elif price_num <= 9999:
        return "🔔つなぐ　新着通知"
    else:
        return "📝つなぐ　新着通知"


# -----------------------------
# embed 色
# -----------------------------
def get_embed_color(price_num):
    if price_num <= 5000:
        return 0xE74C3C
    elif price_num <= 9999:
        return 0x3498DB
    else:
        return 0x2ECC71


# -----------------------------
# HTML解析（誤検出ゼロ版）
# -----------------------------
def parse_items(soup, mode: str):
    items = []
    cards = soup.find_all(class_="p-product")

    for c in cards:
        title_tag = c.find(class_="title")

        price_tag = c.find("p", class_=lambda x: x and "text-danger" in x)

        if not price_tag:
            for tag in c.find_all(["p", "h2", "h3"]):
                text = tag.get_text(strip=True)
                digits = "".join(ch for ch in text if ch.isdigit())
                if digits and ("円" in text or "¥" in text):
                    price_tag = tag
                    break

        raw_price = price_tag.get_text(strip=True) if price_tag else ""
        price = normalize_price(raw_price)

        buy_now = None
        buy_now_tag = c.find("h2")
        if buy_now_tag and ("即決" in buy_now_tag.text or "即決価格" in buy_now_tag.text):
            digits = "".join(ch for ch in buy_now_tag.text if ch.isdigit())
            if digits:
                buy_now = normalize_price(buy_now_tag.text)

        thumb_tag = c.find("img")
        url_tag = c.find("a")

        title = title_tag.get_text(strip=True) if title_tag else ""
        thumb = thumb_tag["src"] if thumb_tag and thumb_tag.has_attr("src") else ""

        url = url_tag["href"] if url_tag and url_tag.has_attr("href") else ""
        if url.startswith("/"):
            url = "https://tsunagu.cloud" + url

        items.append(
            {
                "title": title,
                "price": price,
                "buy_now": buy_now,
                "thumb": thumb,
                "url": url,
                "mode": mode,
            }
        )

    return items


# -----------------------------
# embed生成
# -----------------------------
def build_embed(item):
    price_num = int(item["price"].replace("円", "").replace(",", ""))
    color = get_embed_color(price_num)
    short_url = get_short_url(item["url"])

    fields = [
        {"name": "URL", "value": short_url, "inline": False},
        {"name": "販売形式", "value": "既存販売" if item["mode"] == "exist" else "オークション", "inline": True},
        {"name": "価格", "value": item["price"], "inline": True},
    ]

    if item.get("buy_now"):
        fields.append({"name": "即決価格", "value": item["buy_now"], "inline": True})

    image_url = validate_image_url(item["thumb"])

    embed = {
        "title": item["title"][:256],
        "url": short_url,
        "color": color,
        "fields": fields,
    }

    if image_url:
        embed["image"] = {"url": image_url}

    return embed


# -----------------------------
# メイン処理
# -----------------------------
def main():
    global seller_cache
    seller_cache = load_json(DATA_SELLER_CACHE, default={})
    last_all = load_json(DATA_LAST_ALL, default={})

    if len(last_all) > 100:
        last_all = dict(list(last_all.items())[-100:])

    if len(seller_cache) > 1000:
        seller_cache = dict(list(seller_cache.items())[-500:])

    if is_morning_summary():
        pending_exist = load_json(DATA_PENDING_EXIST, default=[])
        pending_auction = load_json(DATA_PENDING_AUCTION, default=[])
        all_pending = (pending_exist + pending_auction)[:10]

        if all_pending:
            send_discord(WEBHOOK_URL, content="🌅 深夜帯まとめ通知", embeds=all_pending)

        clear_json(DATA_PENDING_EXIST)
        clear_json(DATA_PENDING_AUCTION)

    html_exist = fetch_html(URL_EXIST)
    html_auction = fetch_html(URL_AUCTION)

    if "p-product" not in html_exist and "p-product" not in html_auction:
        return

    soup_exist = parse_html(html_exist)
    soup_auction = parse_html(html_auction)

    items_exist = parse_items(soup_exist, "exist") if soup_exist else []
    items_auction = parse_items(soup_auction, "auction") if soup_auction else []

    new_items = items_exist + items_auction
    new_items.sort(key=lambda x: int(x["price"].replace("円", "").replace(",", "")))

    embeds_to_send = []

    for item in new_items:
        clean_url = normalize_item_url(item["url"])
        h = generate_item_hash(clean_url)

        if h in last_all:
            continue

        price_num = int(item["price"].replace("円", "").replace(",", ""))
        if price_num >= 15000:
            last_all[h] = True
            continue

        seller_id = fetch_seller_id_from_detail(item["url"])
        item["seller_id"] = seller_id

        if not seller_id:
            last_all[h] = True
            continue

        if seller_id in EXCLUDE_USERS:
            last_all[h] = True
            continue

        if is_night():
            pending_path = DATA_PENDING_EXIST if item["mode"] == "exist" else DATA_PENDING_AUCTION
            pending = load_json(pending_path, default=[])
            if len(pending) < 10:
                append_json_list(pending_path, item)
            last_all[h] = True
            continue

        if len(embeds_to_send) < 10:
            embeds_to_send.append(build_embed(item))

        last_all[h] = True

    if embeds_to_send:
        first_price = int(embeds_to_send[0]["fields"][2]["value"].replace("円", "").replace(",", ""))
        title = get_notification_title(first_price)

        try:
            send_discord(WEBHOOK_URL, content=title, embeds=embeds_to_send)
        except Exception:
            pass
        finally:
            save_json(DATA_LAST_ALL, last_all)
            save_json(DATA_SELLER_CACHE, seller_cache)
            return

    save_json(DATA_LAST_ALL, last_all)
    save_json(DATA_SELLER_CACHE, seller_cache)


if __name__ == "__main__":
    safe_run(main)
