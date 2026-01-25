# ============================
# インポート
# ============================

import argparse
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
# 引数
# ============================

def parse_args():
    parser = argparse.ArgumentParser()

    # ログ制御
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--debug", action="store_true")

    # 時間帯強制
    parser.add_argument("--force-night", action="store_true")
    parser.add_argument("--force-day", action="store_true")

    # 通知制御
    parser.add_argument("--dry-run", action="store_true")

    # Cloudflare 対策
    parser.add_argument("--retry", type=int, default=1)

    # seller_cache を無視して再取得
    parser.add_argument("--no-cache", action="store_true")

    return parser.parse_args()


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

MAX_LAST = 5000
THIRTY_DAYS = 60 * 60 * 24 * 30


# ============================
# ユーザー設定読み込み
# ============================

def load_exclude_users(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip() and not line.startswith("#")}
    except FileNotFoundError:
        return set()


EXCLUDE_USERS = load_exclude_users("config/exclude_users.txt")


def load_special_users(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip() and not line.startswith("#")}
    except FileNotFoundError:
        return set()


SPECIAL_USERS = load_special_users("config/special_users.txt")


# ============================
# ユーティリティ
# ============================

def now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def is_night():
    h = now().hour
    return 2 <= h < 6


def is_night_forced(args):
    if args.force_night:
        return True
    if args.force_day:
        return False
    return is_night()


def is_morning():
    t = now()
    return t.hour == 6 and t.minute == 0


def normalize_price(s):
    digits = "".join(c for c in s if c.isdigit())
    return f"{int(digits):,}円" if digits else "0円"


# URL 正規化（商品ID部分だけを抽出・揺れ吸収）
_URL_RE = re.compile(r"(?:https?:)?//?[^/]*?(auctions|exist_products)/(\d+)")

def normalize_url(url):
    m = _URL_RE.search(url)
    if m:
        category = m.group(1)
        item_id = m.group(2)
        return f"{category}/{item_id}"
    return url.strip().rstrip("/")


# ============================
# Cloudflare に強い HTML fetch
# ============================

def fetch_html(url, retry=1):
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

    for t in range(retry):
        try:
            r = requests.get(url, headers=headers, proxies=proxies, timeout=6)
            r.raise_for_status()
            return r.text
        except Exception:
            time.sleep(1.2 * (t + 1))

    return ""


# ============================
# seller_id 抽出
# ============================

seller_cache = {}

def fetch_seller_id(url, no_cache=False):
    if not no_cache and url in seller_cache:
        return seller_cache[url]

    html = fetch_html(url)
    if not html:
        seller_cache[url] = ""
        return ""

    soup = parse_html(html)
    if not soup:
        seller_cache[url] = ""
        return ""

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
# HTML 解析
# ============================

def parse_items(soup, mode):
    items = []

    for c in soup.find_all(class_="p-product"):
        t = c.find(class_="title")
        title = t.get_text(strip=True) if t else ""

        price_tag = c.find("p", class_=lambda x: x and "text-danger" in x)
        if not price_tag:
            for tag in c.find_all(["p", "h2", "h3"]):
                txt = tag.get_text(strip=True)
                if ("円" in txt or "¥" in txt) and any(ch.isdigit() for ch in txt):
                    price_tag = tag
                    break

        price = normalize_price(price_tag.get_text(strip=True) if price_tag else "")

        buy_now = None
        h2 = c.find("h2")
        if h2 and ("即決" in h2.text):
            buy_now = normalize_price(h2.text)

        url = c.find("a")["href"]
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = "https://tsunagu.cloud" + url

        img_tag = c.find("img")
        thumb = img_tag["src"] if img_tag else ""

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


# ============================
# embed 生成（優先度＋色）
# ============================

def build_embed(item, seller):
    p = int(item["price"].replace("円", "").replace(",", ""))

    if seller in SPECIAL_USERS:
        priority_icon = "💌"
        priority_label = "優先"
        color = 0xFF66AA
    else:
        if p <= 3000:
            priority_icon = "🔥"
            priority_label = "特選"
            color = 0xFF4444
        elif p <= 5000:
            priority_icon = "⭐"
            priority_label = "注目"
            color = 0xFFDD33
        elif p <= 10000:
            priority_icon = "✨"
            priority_label = "おすすめ"
            color = 0xF28C28
        else:
            priority_icon = ""
            priority_label = "通常"
            color = 0x66CCFF

    short = get_short_url(item["url"])

    fields = [
        {
            "name": "優先度",
            "value": f"{priority_icon} {priority_label}".strip(),
            "inline": True,
        },
        {
            "name": "販売形式",
            "value": "既存販売" if item["mode"] == "exist" else "オークション",
            "inline": True,
        },
        {
            "name": "価格",
            "value": item["price"],
            "inline": True,
        },
    ]

    if item["buy_now"]:
        fields.append(
            {
                "name": "即決価格",
                "value": item["buy_now"],
                "inline": True,
            }
        )

    embed = {
        "title": item["title"][:256],
        "url": short,
        "color": color,
        "fields": fields,
        "seller": seller,
    }

    img = validate_image_url(item["thumb"])
    if img:
        embed["image"] = {"url": img}

    return embed


# ============================
# 優先度ソート
# ============================

def embed_priority(e):
    seller = e.get("seller", "")
    if seller in SPECIAL_USERS:
        pri = 0
    else:
        v = e["fields"][0]["value"]
        if "特選" in v:
            pri = 1
        elif "注目" in v:
            pri = 2
        elif "おすすめ" in v:
            pri = 3
        else:
            pri = 4

    mode_priority = 0 if e["fields"][1]["value"] == "既存販売" else 1
    price = int(e["fields"][2]["value"].replace("円", "").replace(",", ""))
    return (pri, mode_priority, price)


# ============================
# main
# ============================

def main(args):
    global seller_cache

    seller_cache = load_json(DATA_SELLER, default={})
    last = load_json(DATA_LAST, default={})

    now_ts = int(time.time())

    # 古い last を整理（30日以上前を削除）
    last = {h: ts for h, ts in last.items() if isinstance(ts, int) and now_ts - ts < THIRTY_DAYS}

    try:
        # 朝6時まとめ通知
        if is_morning() and not args.force_night:
            pending = load_json(DATA_PENDING_EXIST, default=[]) + load_json(
                DATA_PENDING_AUCTION, default=[]
            )
            if pending and not args.dry_run:
                send_discord(WEBHOOK_URL, "🌅 深夜帯まとめ通知", pending[:10])

            clear_json(DATA_PENDING_EXIST)
            clear_json(DATA_PENDING_AUCTION)

        soup_exist = parse_html(fetch_html(URL_EXIST, retry=args.retry))
        soup_auction = parse_html(fetch_html(URL_AUCTION, retry=args.retry))

        items = []
        if soup_exist:
            items += parse_items(soup_exist, "exist")
        if soup_auction:
            items += parse_items(soup_auction, "auction")

        items.sort(key=lambda x: int(x["price"].replace("円", "").replace(",", "")))

        embeds = []

        for item in items:
            key = normalize_url(item["url"])
            if not key:
                continue

            h = generate_item_hash(key)

            if h in last:
                continue

            price = int(item["price"].replace("円", "").replace(",", ""))

            seller = fetch_seller_id(item["url"], no_cache=args.no_cache)

            if seller in SPECIAL_USERS:
                if len(embeds) < 10:
                    embeds.append(build_embed(item, seller))
                last[h] = now_ts
                continue

            if price >= 15000:
                last[h] = now_ts
                continue

            if not seller or seller in EXCLUDE_USERS:
                last[h] = now_ts
                continue

            if is_night_forced(args):
                path = DATA_PENDING_EXIST if item["mode"] == "exist" else DATA_PENDING_AUCTION
                append_json_list(path, item)
                last[h] = now_ts
                continue

            if len(embeds) < 10:
                embeds.append(build_embed(item, seller))

            last[h] = now_ts

        if embeds:
            embeds.sort(key=embed_priority)

            contains_special = any(e.get("seller") in SPECIAL_USERS for e in embeds)

            if contains_special:
                title = "@everyone\n💌つなぐ 優先通知"
            else:
                first_label = embeds[0]["fields"][0]["value"]
                if "特選" in first_label:
                    title = "🔥つなぐ 特選通知"
                elif "注目" in first_label:
                    title = "⭐つなぐ 注目通知"
                elif "おすすめ" in first_label:
                    title = "✨つなぐ おすすめ通知"
                else:
                    title = "📝つなぐ 通常通知"

            if args.dry_run:
                if not args.quiet:
                    print("=== DRY RUN ===")
                    print(title)
                    for e in embeds:
                        print(e)
            else:
                # last のローテーション（件数制限）
                if len(last) > MAX_LAST:
                    sorted_items = sorted(last.items(), key=lambda x: x[1])
                    last = dict(sorted_items[-MAX_LAST:])

                ok = send_discord(WEBHOOK_URL, title, embeds)
                if ok:
                    save_json(DATA_LAST, last)
                else:
                    if not args.quiet:
                        print("送信失敗のため last_all.json は更新しません")

    finally:
        save_json(DATA_SELLER, seller_cache)


# ============================
# エントリーポイント
# ============================

if __name__ == "__main__":
    args = parse_args()
    main(args)
