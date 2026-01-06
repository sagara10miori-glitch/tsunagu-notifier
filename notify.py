import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime, time
import os

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")


# ---------------------------------------------------------
# 深夜帯判定（0:30〜7:30 は @everyone を外す）
# ---------------------------------------------------------
def is_quiet_hours():
    now = datetime.now().time()
    return time(0, 30) <= now <= time(7, 30)


# ---------------------------------------------------------
# HTML取得
# ---------------------------------------------------------
def fetch_html(url):
    r = requests.get(url, timeout=10)
    return BeautifulSoup(r.text, "html.parser")


# ---------------------------------------------------------
# 既存販売の取得（安全版）
# ---------------------------------------------------------
def fetch_exist_items():
    url = "https://tsunagu.cloud/products"
    soup = fetch_html(url)
    cards = soup.select(".p-product")

    items = []
    for card in cards:
        # 画像がないカードはスキップ
        img_tag = card.select_one(".image-1-1 img")
        if not img_tag:
            continue

        # リンクがないカードはスキップ
        link_tag = card.select_one("a")
        if not link_tag:
            continue

        link = link_tag["href"]
        item_id = link.split("/")[-1]

        # タイトルがないカードはスキップ
        title_tag = card.select_one(".title")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)

        img = img_tag["src"]

        # 作者アイコン
        author_icon_tag = card.select_one(".avatar img")
        author_icon = author_icon_tag["src"] if author_icon_tag else ""

        # 価格
        price_tag = card.select_one(".text-danger")
        price = price_tag.get_text(strip=True) if price_tag else "0"

        # 詳細ページから作者ID取得
        detail = fetch_html(link)
        author_link = detail.select_one(".user-name a")
        author_id = author_link["href"].split("/")[-1] if author_link else ""

        items.append({
            "id": item_id,
            "title": title,
            "img": img,
            "price": price,
            "link": link,
            "author_icon": author_icon,
            "author_id": author_id,
            "sale_type": "既存販売"
        })

    return items


# ---------------------------------------------------------
# オークションの取得（安全版）
# ---------------------------------------------------------
def fetch_auction_items():
    url = "https://tsunagu.cloud/auctions"
    soup = fetch_html(url)
    cards = soup.select(".p-product")

    items = []
    for card in cards:
        img_tag = card.select_one(".image-1-1 img")
        if not img_tag:
            continue

        link_tag = card.select_one("a")
        if not link_tag:
            continue

        link = link_tag["href"]
        item_id = link.split("/")[-1]

        title_tag = card.select_one(".title")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)

        img = img_tag["src"]

        author_icon_tag = card.select_one(".avatar img")
        author_icon = author_icon_tag["src"] if author_icon_tag else ""

        # 価格が2つ揃っていないカードはスキップ
        prices = card.select("p.h2")
        if len(prices) < 2:
            continue

        current_price = prices[0].get_text(strip=True)
        buyout_price = prices[1].get_text(strip=True)

        detail = fetch_html(link)
        author_link = detail.select_one(".user-name a")
        author_id = author_link["href"].split("/")[-1] if author_link else ""

        items.append({
            "id": item_id,
            "title": title,
            "img": img,
            "current_price": current_price,
            "buyout_price": buyout_price,
            "link": link,
            "author_icon": author_icon,
            "author_id": author_id,
            "sale_type": "オークション"
        })

    return items


# ---------------------------------------------------------
# 条件判定（全体通知用）
# ---------------------------------------------------------
def match_global_conditions(item):
    # 既存販売：5000円以下
    if item["sale_type"] == "既存販売":
        return int(item["price"].replace(",", "")) <= 5000

    # オークション：現在 or 即決が5000円以下
    if item["sale_type"] == "オークション":
        now_price = int(item["current_price"].replace(",", ""))
        buy_price = int(item["buyout_price"].replace(",", ""))
        return now_price <= 5000 or buy_price <= 5000

    return False


# ---------------------------------------------------------
# バッチ送信
# ---------------------------------------------------------
def send_discord_batch(items, is_first):
    if is_quiet_hours():
        mention = ""
    else:
        mention = "@everyone" if is_first else ""

    separator = "✦━━━━━━━━━━━━✦"
    content = f"{separator}\n{mention}" if mention else separator

    embeds = []

    for item in items:
        # 色分け
        if item["sale_type"] == "既存販売":
            base_color = 0x5EB7E8
        elif item["sale_type"] == "オークション":
            base_color = 0x0033AA
        else:
            base_color = 0x5EB7E8

        color = 0xFFA500 if item["is_user_specific"] else base_color

        embed = {
            "title": item["title"],
            "url": item["link"],
            "color": color,
            "author": {
                "name": "",
                "icon_url": item["author_icon"]
            },
            "image": {"url": item["img"]},
            "fields": [
                {"name": "販売形式", "value": item["sale_type"], "inline": True},
            ]
        }

        if item["sale_type"] == "既存販売":
            embed["fields"].append(
                {"name": "価格", "value": f"{item['price']}円", "inline": True}
            )

        if item["sale_type"] == "オークション":
            embed["fields"].append(
                {"name": "現在価格", "value": f"{item['current_price']}円", "inline": True}
            )
            embed["fields"].append(
                {"name": "即決価格", "value": f"{item['buyout_price']}円", "inline": True}
            )

        embed["fields"].append(
            {"name": "URL", "value": item["link"], "inline": False}
        )

        embeds.append(embed)

    data = {"content": content, "embeds": embeds}
    requests.post(WEBHOOK_URL, json=data)


# ---------------------------------------------------------
# メイン処理
# ---------------------------------------------------------
def main():
    # 既読管理
    last_all = json.load(open("last_all.json")) if os.path.exists("last_all.json") else []
    last_users = json.load(open("last_users.json")) if os.path.exists("last_users.json") else []

    users = [u.strip() for u in open("users.txt").read().splitlines()]

    new_all = []
    new_users = []

    # 取得
    items = fetch_exist_items() + fetch_auction_items()

    batch_user_specific = []
    batch_exist = []
    batch_auction = []

    for item in items:
        is_user_specific = item["author_id"] in users
        item["is_user_specific"] = is_user_specific

        # 特定ユーザー通知（最優先）
        if is_user_specific and item["id"] not in last_users:
            batch_user_specific.append(item)
            new_users.append(item["id"])
            continue

        # 全体通知（カテゴリ別）
        if item["id"] not in last_all and match_global_conditions(item):
            if item["sale_type"] == "既存販売":
                batch_exist.append(item)
            elif item["sale_type"] == "オークション":
                batch_auction.append(item)
            new_all.append(item["id"])

    # 送信順序
    if batch_user_specific:
        send_discord_batch(batch_user_specific, is_first=True)

    if batch_exist:
        send_discord_batch(batch_exist, is_first=False)

    if batch_auction:
        send_discord_batch(batch_auction, is_first=False)

    # 保存
    json.dump(last_all + new_all, open("last_all.json", "w"))
    json.dump(last_users + new_users, open("last_users.json", "w"))


if __name__ == "__main__":
    main()
