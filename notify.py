import os
import datetime
import re

from utils.safety import safe_run
from utils.fetch import fetch_html, parse_html, validate_image_url
from utils.classify import classify_item
from utils.hashgen import generate_item_hash
from utils.shorturl import get_short_url
from utils.storage import load_json, save_json, append_json_list, clear_json
from utils.discord import send_discord

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

# -----------------------------
# 色設定
# -----------------------------
COLOR_EXIST = 0x2ECC71
COLOR_AUCTION = 0x9B59B6
COLOR_SPECIAL = 0xFFD700

# -----------------------------
# 除外ユーザー（ID）
# -----------------------------
def load_exclude_users(path: str) -> set:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip() and not line.startswith("#")}
    except FileNotFoundError:
        return set()

EXCLUDE_USERS = load_exclude_users("config/exclude_users.txt")


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
# 詳細ページからユーザーIDを取得
# -----------------------------
def fetch_seller_id_from_detail(url):
    """商品詳細ページにアクセスしてユーザーIDを取得する"""
    html = fetch_html(url)
    soup = parse_html(html)
    if not soup:
        return ""

    # 出品者プロフィールリンクを探す
    tag = soup.select_one('a[href*="/users/"]')
    if not tag:
        return ""

    href = tag.get("href", "")

    # /users/xxxxxx の部分からIDを抽出
    m = re.search(r"/users/([^/?#]+)", href)
    if m:
        return m.group(1).strip()

    return ""


# -----------------------------
# HTML解析（一覧ページ）
# -----------------------------
def parse_items(soup, mode: str):
    items = []

    cards = soup.select(".p-product")

    for c in cards:
        title_tag = c.select_one(".title")
        title = title_tag.text.strip() if title_tag else ""

        price_tag = c.select_one(".text-danger") or c.select_one(".h3")
        raw_price = price_tag.text.strip() if price_tag else ""
        price = normalize_price(raw_price)

        buy_now_tag = c.select_one(".small .h2:not(.text-danger)")
        raw_buy_now = buy_now_tag.text.strip() if buy_now_tag else None
        buy_now = normalize_price(raw_buy_now) if raw_buy_now else None

        thumb_tag = c.select_one(".image-1-1 img")
        thumb = thumb_tag["src"] if thumb_tag and thumb_tag.has_attr("src") else ""

        url_tag = c.select_one("a")
        url = url_tag["href"] if url_tag and url_tag.has_attr("href") else ""
        if url.startswith("/"):
            url = "https://tsunagu.cloud" + url

        items.append({
            "title": title,
            "price": price,
            "buy_now": buy_now,
            "thumb": thumb,
            "url": url,
            "mode": mode,
        })

    return items


# -----------------------------
# embed生成
# -----------------------------
def build_embed(item, is_special: bool):
    short_url = get_short_url(item["url"])

    color = COLOR_SPECIAL if is_special else (
        COLOR_EXIST if item["mode"] == "exist" else COLOR_AUCTION
    )

    fields = [
        {"name": "URL", "value": short_url, "inline": False},
        {"name": "販売形式", "value": "既存販売" if item["mode"] == "exist" else "オークション", "inline": True},
        {"name": "価格", "value": item["price"], "inline": True},
        {"name": "出品者ID", "value": item["seller_id"], "inline": True},
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
    last_all = load_json(DATA_LAST_ALL, default={})

    # -----------------------------
    # 朝6時まとめ通知（最大10件）
    # -----------------------------
    if is_morning_summary():
        pending_exist = load_json(DATA_PENDING_EXIST, default=[])
        pending_auction = load_json(DATA_PENDING_AUCTION, default=[])

        all_pending = (pending_exist + pending_auction)[:10]

        if all_pending:
            send_discord(WEBHOOK_URL, content="🌅 深夜帯まとめ通知", embeds=all_pending)

        clear_json(DATA_PENDING_EXIST)
        clear_json(DATA_PENDING_AUCTION)

    # -----------------------------
    # HTML取得
    # -----------------------------
    html_exist = fetch_html(URL_EXIST)
    html_auction = fetch_html(URL_AUCTION)

    with open("debug_exist.html", "w", encoding="utf-8") as f:
        f.write(html_exist)
    with open("debug_auction.html", "w", encoding="utf-8") as f:
        f.write(html_auction)

    if "p-product" not in html_exist and "p-product" not in html_auction:
        print("[ERROR] 商品が取得できませんでした。今回の実行はスキップします。")
        return

    soup_exist = parse_html(html_exist)
    soup_auction = parse_html(html_auction)

    if not soup_exist or not soup_auction:
        print("[ERROR] HTML parse failed")
        return

    items_exist = parse_items(soup_exist, "exist")
    items_auction = parse_items(soup_auction, "auction")

    new_items = items_exist + items_auction

    # -----------------------------
    # 新着チェック（最大10件）
    # -----------------------------
    embeds_to_send = []

    for item in new_items:
        h = generate_item_hash(item["url"])

        if h in last_all:
            continue

        # ★ 詳細ページからユーザーIDを取得
        seller_id = fetch_seller_id_from_detail(item["url"])
        item["seller_id"] = seller_id

        # ★ 除外ユーザー判定（IDベース）
        if seller_id in EXCLUDE_USERS:
            last_all[h] = True
            continue

        # 価格フィルター
        price_num = int(item["price"].replace("円", "").replace(",", ""))
        if price_num >= 15000:
            last_all[h] = True
            continue

        # 深夜帯 → pending
        if is_night():
            pending_path = DATA_PENDING_EXIST if item["mode"] == "exist" else DATA_PENDING_AUCTION
            pending = load_json(pending_path, default=[])
            if len(pending) < 10:
                append_json_list(pending_path, item)
            last_all[h] = True
            continue

        # 通知は最大10件
        if len(embeds_to_send) < 10:
            embeds_to_send.append(build_embed(item, is_special=False))

        last_all[h] = True

    # -----------------------------
    # 通知送信（最大10件）
    # -----------------------------
    if embeds_to_send:
        send_discord(WEBHOOK_URL, content="🔔 新着通知", embeds=embeds_to_send)

    save_json(DATA_LAST_ALL, last_all)


# -----------------------------
# 実行
# -----------------------------
if __name__ == "__main__":
    safe_run(main)
