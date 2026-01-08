import os
import datetime
from utils.safety import safe_run
from utils.fetch import fetch_html, parse_html, get_html_hash, detect_structure_change
from utils.classify import classify_item
from utils.hashgen import generate_item_hash
from utils.shorturl import get_short_url
from utils.storage import load_json, save_json, append_json_list, clear_json
from utils.discord import send_discord

# -----------------------------
# 設定
# -----------------------------
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

URL_EXIST = "https://tsunagu.cloud/exist_products?sort=&exist_product_category_id=2&exist_product_category2_id=2&exist_product_category3_id=&keyword=&max_sales_count_exist_items=1&is_selling=true&is_ai_content=0"
URL_AUCTION = "https://tsunagu.cloud/auctions?sort=&exist_product_category_id=2&exist_product_category2_id=2&exist_product_category3_id=&keyword=&is_disp_progress=1&is_ai_content=0"

DATA_LAST_ALL = "data/last_all.json"
DATA_LAST_SPECIAL = "data/last_special.json"
DATA_PENDING_EXIST = "data/pending_night_exist.json"
DATA_PENDING_AUCTION = "data/pending_night_auction.json"

SPECIAL_USERS = "config/special_users.txt"
EXCLUDE_USERS = "config/exclude_users.txt"

# -----------------------------
# 色設定
# -----------------------------
COLOR_EXIST = 0x2ECC71      # 緑
COLOR_AUCTION = 0x9B59B6    # 紫
COLOR_SPECIAL = 0xFFD700    # 金色


# -----------------------------
# ユーティリティ
# -----------------------------
def load_list(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def is_night():
    now = datetime.datetime.now().hour
    return 2 <= now < 6


def is_morning_summary():
    now = datetime.datetime.now()
    return now.hour == 6 and now.minute == 0


# -----------------------------
# HTML解析（つなぐ専用）
# -----------------------------
def parse_items(soup, mode):
    """
    mode: "exist" or "auction"
    """
    items = []

    cards = soup.select(".product-card, .auction-card")
    for c in cards:
        title = c.select_one(".product-title, .auction-title")
        author = c.select_one(".product-author, .auction-author")
        price = c.select_one(".product-price, .auction-price")
        thumb = c.select_one("img")

        title = title.text.strip() if title else ""
        author = author.text.strip() if author else ""
        price = price.text.strip() if price else ""
        thumb = thumb["src"] if thumb else ""

        url_tag = c.select_one("a")
        url = "https://tsunagu.cloud" + url_tag["href"] if url_tag else ""

        items.append({
            "title": title,
            "author": author,
            "price": price,
            "thumb": thumb,
            "url": url,
            "mode": mode
        })

    return items


# -----------------------------
# embed生成
# -----------------------------
def build_embed(item, is_special):
    short_url = get_short_url(item["url"])

    color = COLOR_SPECIAL if is_special else (
        COLOR_EXIST if item["mode"] == "exist" else COLOR_AUCTION
    )

    return {
        "title": item["title"],
        "url": short_url,
        "color": color,
        "thumbnail": {"url": item["thumb"]},
        "fields": [
            {"name": "作者", "value": item["author"], "inline": True},
            {"name": "価格", "value": item["price"], "inline": True},
            {"name": "カテゴリ", "value": "既存販売" if item["mode"] == "exist" else "オークション", "inline": True}
        ]
    }


# -----------------------------
# メイン処理
# -----------------------------
def main():
    # -----------------------------
    # データ読み込み
    # -----------------------------
    last_all = load_json(DATA_LAST_ALL, default={})
    last_special = load_json(DATA_LAST_SPECIAL, default={})

    special_users = load_list(SPECIAL_USERS)
    exclude_users = load_list(EXCLUDE_USERS)

    # -----------------------------
    # 朝6時 → 深夜帯まとめ通知
    # -----------------------------
    if is_morning_summary():
        embeds = []

        pending_exist = load_json(DATA_PENDING_EXIST, default=[])
        pending_auction = load_json(DATA_PENDING_AUCTION, default=[])

        for item in pending_exist + pending_auction:
            embeds.append(build_embed(item, is_special=False))

        if embeds:
            send_discord(WEBHOOK_URL, content="🌅 深夜帯まとめ通知", embeds=embeds)

        clear_json(DATA_PENDING_EXIST)
        clear_json(DATA_PENDING_AUCTION)

    # -----------------------------
    # HTML取得
    # -----------------------------
    html_exist = fetch_html(URL_EXIST)
    html_auction = fetch_html(URL_AUCTION)

    soup_exist = parse_html(html_exist)
    soup_auction = parse_html(html_auction)

    if not soup_exist or not soup_auction:
        print("[ERROR] HTML parse failed")
        return

    items_exist = parse_items(soup_exist, "exist")
    items_auction = parse_items(soup_auction, "auction")

    new_items = items_exist + items_auction

    # -----------------------------
    # 新着チェック
    # -----------------------------
    embeds_to_send = []

    for item in new_items:
        h = generate_item_hash(item["title"], item["author"], item["price"], item["url"])

        # 除外ユーザー
        if item["author"] in exclude_users:
            continue

        # 特別ユーザー
        if item["author"] in special_users:
            if h not in last_special:
                last_special[h] = True
                embeds_to_send.append(build_embed(item, is_special=True))
            continue

        # 通常ユーザー
        if h in last_all:
            continue

        # カテゴリ分類
        category = classify_item(item["title"], "", [])
        if category == "除外":
            continue

        # 深夜帯 → pending に保存
        if is_night():
            if item["mode"] == "exist":
                append_json_list(DATA_PENDING_EXIST, item)
            else:
                append_json_list(DATA_PENDING_AUCTION, item)
            last_all[h] = True
            continue

        # 即時通知
        embeds_to_send.append(build_embed(item, is_special=False))
        last_all[h] = True

    # -----------------------------
    # 通知送信
    # -----------------------------
    if embeds_to_send:
        send_discord(WEBHOOK_URL, content="🔔 新着通知", embeds=embeds_to_send)

    # -----------------------------
    # 保存
    # -----------------------------
    save_json(DATA_LAST_ALL, last_all)
    save_json(DATA_LAST_SPECIAL, last_special)


# -----------------------------
# 実行
# -----------------------------
if __name__ == "__main__":
    safe_run(main)
