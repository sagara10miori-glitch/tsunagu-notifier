import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime, time
import os
import re

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

TARGET_USER = "fruit_fulful"


def is_quiet_hours():
    now = datetime.now().time()
    return time(0, 30) <= now <= time(7, 30)


def is_special_time():
    now = datetime.now()
    return now.weekday() == 6 and time(21, 0) <= now.time() <= time(22, 0)


def fetch_html(url):
    r = requests.get(url, timeout=10)
    return BeautifulSoup(r.text, "html.parser")


def extract_stable_id_from_url(url):
    return url.rstrip("/").split("/")[-1]


def to_number(text):
    num = re.sub(r"\D", "", text)
    return int(num) if num else 0


def fetch_exist_items():
    url = "https://tsunagu.cloud/exist_products?page=1"
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
        item_id = extract_stable_id_from_url(link)

        title_tag = card.select_one(".title")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)

        img = img_tag["src"]

        author_icon_tag = card.select_one(".avatar img")
        author_icon = author_icon_tag["src"] if author_icon_tag else ""

        price_tag = (
            card.select_one(".text-danger") or
            card.select_one(".price") or
            card.select_one(".text-primary") or
            card.select_one(".h3") or
            card.select_one(".h2") or
            card.select_one(".value")
        )
        if not price_tag:
            continue

        price = price_tag.get_text(strip=True)

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


def fetch_auction_items():
    url = "https://tsunagu.cloud/auctions?page=1"
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
        item_id = extract_stable_id_from_url(link)

        title_tag = card.select_one(".title")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)

        img = img_tag["src"]

        author_icon_tag = card.select_one(".avatar img")
        author_icon = author_icon_tag["src"] if author_icon_tag else ""

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


def match_global_conditions(item):
    if item["sale_type"] == "既存販売":
        return to_number(item["price"]) <= 5000

    if item["sale_type"] == "オークション":
        return (
            to_number(item["current_price"]) <= 5000 or
            to_number(item["buyout_price"]) <= 5000
        )

    return False


def send_discord_batch(items):
    mention = "" if is_quiet_hours() else "@everyone"

    embeds = []
    for item in items:
        color = 0x5EB7E8 if item["sale_type"] == "既存販売" else 0x0033AA

        embed = {
            "title": item["title"],
            "url": item["link"],
            "color": color,
            "author": {"name": "", "icon_url": item["author_icon"]},
            "image": {"url": item["img"]},
            "fields": [
                {"name": "販売形式", "value": item["sale_type"], "inline": True},
            ]
        }

        if item["sale_type"] == "既存販売":
            embed["fields"].append({"name": "価格", "value": item["price"], "inline": True})

        if item["sale_type"] == "オークション":
            embed["fields"].append({"name": "現在価格", "value": item["current_price"], "inline": True})
            embed["fields"].append({"name": "即決価格", "value": item["buyout_price"], "inline": True})

        embed["fields"].append({"name": "URL", "value": item["link"], "inline": False})

        embeds.append(embed)

    data = {"content": mention, "embeds": embeds}
    requests.post(WEBHOOK_URL, json=data)


def send_special_batch(items):
    embeds = []
    for item in items:
        embed = {
            "title": f"[特別ユーザー] {item['title']}",
            "url": item["link"],
            "color": 0xFFA500,
            "author": {"name": "", "icon_url": item["author_icon"]},
            "image": {"url": item["img"]},
            "fields": [
                {"name": "販売形式", "value": item["sale_type"], "inline": True},
                {"name": "URL", "value": item["link"], "inline": False}
            ]
        }
        embeds.append(embed)

    data = {"content": "@everyone", "embeds": embeds}
    requests.post(WEBHOOK_URL, json=data)


def main():
    last_all = json.load(open("last_all.json")) if os.path.exists("last_all.json") else []
    last_special = json.load(open("last_special.json")) if os.path.exists("last_special.json") else []

    new_all = []
    new_special = []

    items = fetch_exist_items() + fetch_auction_items()

    batch_exist = []
    batch_auction = []
    batch_special = []

    for item in items:
        if is_special_time():
            if item["author_id"] == TARGET_USER and item["id"] not in last_special:
                batch_special.append(item)
                new_special.append(item["id"])
                continue

        if item["id"] not in last_all and match_global_conditions(item):
            if item["sale_type"] == "既存販売":
                batch_exist.append(item)
            elif item["sale_type"] == "オークション":
                batch_auction.append(item)
            new_all.append(item["id"])

    if batch_special:
        send_special_batch(batch_special)

    if batch_exist:
        send_discord_batch(batch_exist)

    if batch_auction:
        send_discord_batch(batch_auction)

    json.dump(last_all + new_all, open("last_all.json", "w"))
    json.dump(last_special + new_special, open("last_special.json", "w"))


if __name__ == "__main__":
    main()
