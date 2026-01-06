import requests
from bs4 import BeautifulSoup
import json
import os

URL = "https://tsunagu.cloud/exist_products?exist_product_category2_id=2&max_sales_count_exist_items=1&is_ai_content=0"
HEADERS = {"User-Agent": "Mozilla/5.0"}

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")


# -------------------------
# JSON 読み書き
# -------------------------
def load_json(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except:
        return []


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# -------------------------
# users.txt 読み込み
# -------------------------
def load_users():
    if not os.path.exists("users.txt"):
        return []
    with open("users.txt", "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


# -------------------------
# 価格抽出
# -------------------------
def extract_price(text):
    return int(text.replace("円", "").replace(",", "").strip())


# -------------------------
# Discord 通知
# -------------------------
def send_discord(item, is_first):
    content = "@everyone" if is_first else ""

    embed = {
        "title": item["title"],
        "url": item["link"],
        "color": 0x5EB7E8,  # 統一カラー
        "image": {"url": item["img"]},
        "fields": [
            {"name": "価格", "value": f"{item['price']}円", "inline": True},
            {"name": "作者", "value": item["author"], "inline": True},
            {"name": "URL", "value": item["link"], "inline": False},
        ]
    }

    data = {"content": content, "embeds": [embed]}
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

        author = card.select_one(".user-name").get_text(strip=True)
        author_id = card.select_one(".user-name a")["href"].split("/")[-1]

        item_id = link.split("/")[-1]

        items.append({
            "id": item_id,
            "title": title,
            "price": price,
            "link": link,
            "img": img,
            "author": author,
            "author_id": author_id
        })

    return items


# -------------------------
# 全体条件フィルタ
# -------------------------
def match_global_conditions(item):
    return item["price"] <= 5000


# -------------------------
# メイン処理
# -------------------------
def main():
    users = load_users()

    last_all = load_json("last_data_all.json")
    last_users = load_json("last_data_users.json")

    items = fetch_items()

    is_first_all = (len(last_all) == 0)
    is_first_users = (len(last_users) == 0)

    new_all = last_all.copy()
    new_users = last_users.copy()

    for item in items:

        # --- 全体条件 ---
        if item["id"] not in last_all and match_global_conditions(item):
            send_discord(item, is_first_all)
            new_all.append(item["id"])
            is_first_all = False

        # --- 特定ユーザー条件 ---
        if item["author_id"] in users and item["id"] not in last_users:
            send_discord(item, is_first_users)
            new_users.append(item["id"])
            is_first_users = False

    save_json("last_data_all.json", new_all)
    save_json("last_data_users.json", new_users)


if __name__ == "__main__":
    main()
