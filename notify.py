import requests
from bs4 import BeautifulSoup
import json
import os

URL = "https://tsunagu.cloud/exist_products?exist_product_category2_id=2&max_sales_count_exist_items=1&is_ai_content=0"
HEADERS = {"User-Agent": "Mozilla/5.0"}

WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK_URL"  # ← ここに入れる


# -------------------------
# JSON 読み書き
# -------------------------
def load_last_data():
    if not os.path.exists("last_data.json"):
        return []
    with open("last_data.json", "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []


def save_last_data(data):
    with open("last_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# -------------------------
# 価格抽出
# -------------------------
def extract_price(text):
    return int(text.replace("円", "").replace(",", "").strip())


# -------------------------
# Discord 通知
# -------------------------
def send_discord(item):
    embed = {
        "title": item["title"],
        "url": item["link"],
        "thumbnail": {"url": item["img"]},
        "fields": [
            {"name": "価格", "value": f"{item['price']}円", "inline": True},
        ]
    }

    data = {"embeds": [embed]}
    requests.post(WEBHOOK_URL, json=data)


# -------------------------
# 商品取得（スクレイピング）
# -------------------------
def fetch_items():
    res = requests.get(URL, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")

    items = []

    for card in soup.select(".p-product"):
        a = card.select_one("a")
        link = a["href"]

        img = card.select_one(".image-1-1 img")["src"]
        title = card.select_one(".title").get_text(strip=True)
        price_text = card.select_one(".h3").get_text(strip=True)
        price = extract_price(price_text)

        item_id = link.split("/")[-1]  # 商品IDを抽出

        items.append({
            "id": item_id,
            "title": title,
            "price": price,
            "link": link,
            "img": img
        })

    return items


# -------------------------
# 条件フィルタ（あなたの条件）
# -------------------------
def match_conditions(item):
    # 5000円以内
    if item["price"] > 5000:
        return False

    # 立ち絵・1人限定・非AI は URL 側で絞っているので不要

    return True


# -------------------------
# メイン処理
# -------------------------
def main():
    last_ids = load_last_data()
    items = fetch_items()

    new_ids = last_ids.copy()

    for item in items:
        if item["id"] not in last_ids and match_conditions(item):
            send_discord(item)
            new_ids.append(item["id"])

    save_last_data(new_ids)


if __name__ == "__main__":
    main()
