# ============================
# インポート
# ============================

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


# ============================
# ユーザー設定読み込み
# ============================

def load_exclude_users(path):
    """除外ユーザー一覧を読み込む"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip() and not line.startswith("#")}
    except FileNotFoundError:
        return set()


EXCLUDE_USERS = load_exclude_users("config/exclude_users.txt")


def load_special_users(path):
    """優先通知ユーザー一覧を読み込む"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip() and not line.startswith("#")}
    except FileNotFoundError:
        return set()


SPECIAL_USERS = load_special_users("config/special_users.txt")


# ============================
# ユーティリティ
# ============================

# GitHub Actions は UTC で動くため、JST に補正した現在時刻を返す
def now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def is_night():
    """深夜帯（JST 2:00〜5:59）判定"""
    h = now().hour
    return 2 <= h < 6


def is_morning():
    """朝6:00ちょうどのまとめ通知判定"""
    t = now()
    return t.hour == 6 and t.minute == 0


# 価格文字列を正規化（数字抽出 → カンマ付与 → 円）
def normalize_price(s):
    digits = "".join(c for c in s if c.isdigit())
    return f"{int(digits):,}円" if digits else "0円"


# URL 正規化（商品ID部分だけを抽出）
_URL_RE = re.compile(r"(auctions|exist_products)/(\d+)")

def normalize_url(url):
    """商品URLを安定したキーに変換"""
    m = _URL_RE.search(url)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    # パラメータや # を除去
    return url.split("?")[0].split("#")[0].rstrip("/")


# ============================
# Cloudflare に強い HTML fetch
# ============================

def fetch_html(url):
    """
    Cloudflare によるブロックを避けつつ HTML を取得する。
    軽量な retry（指数バックオフ）で安定性を確保。
    """
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

    # 2回 → 3回に増やして安定性UP（仕様は変わらない）
    for t in range(3):
        try:
            r = requests.get(url, headers=headers, proxies=proxies, timeout=6)
            r.raise_for_status()
            return r.text
        except Exception:
            # Cloudflare の一時ブロックに強い指数バックオフ
            time.sleep(1.2 * (t + 1))

    return ""


# ============================
# seller_id 抽出（高速・安定）
# ============================

seller_cache = {}

def fetch_seller_id(url):
    """
    商品ページから seller_id を抽出する。
    - seller_cache により高速化
    - Cloudflare ブロック時も空文字で安全に処理
    """
    if url in seller_cache:
        return seller_cache[url]

    html = fetch_html(url)
    if not html:
        seller_cache[url] = ""
        return ""

    soup = parse_html(html)
    if not soup:
        seller_cache[url] = ""
        return ""

    # /users/ または /profile/ のリンクから seller_id を抽出
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
# seller_id 抽出（高速・安定）
# ============================

seller_cache = {}


def fetch_seller_id(url):
    if url in seller_cache:
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
# HTML 解析（誤検出ゼロ・高速化）
# ============================

def parse_items(soup, mode):
    """
    商品一覧ページから商品情報を抽出する。
    - 価格タグの検出を強化（text-danger が無い場合の fallback）
    - URL の補正（// → https:、/ → https://tsunagu.cloud）
    - 仕様は完全にそのまま
    """
    items = []

    for c in soup.find_all(class_="p-product"):
        # タイトル
        t = c.find(class_="title")
        title = t.get_text(strip=True) if t else ""

        # 価格（text-danger が無い場合の fallback）
        price_tag = c.find("p", class_=lambda x: x and "text-danger" in x)
        if not price_tag:
            # 価格が別タグに入っているケースに対応
            for tag in c.find_all(["p", "h2", "h3"]):
                txt = tag.get_text(strip=True)
                if ("円" in txt or "¥" in txt) and any(ch.isdigit() for ch in txt):
                    price_tag = tag
                    break

        price = normalize_price(price_tag.get_text(strip=True) if price_tag else "")

        # 即決価格（オークションのみ）
        buy_now = None
        h2 = c.find("h2")
        if h2 and ("即決" in h2.text):
            buy_now = normalize_price(h2.text)

        # 商品URL
        url = c.find("a")["href"]
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = "https://tsunagu.cloud" + url

        # サムネイル
        img_tag = c.find("img")
        thumb = img_tag["src"] if img_tag else ""

        # 商品データを追加
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
# embed 生成（短く・美しく・seller保持）
# ============================

def build_embed(item, seller):
    """
    Discord に送る embed を生成する。
    - seller を embed に保持（再取得不要）
    - 価格に応じて色分け（仕様そのまま）
    - サムネイルは validate_image_url で安全に処理
    """
    # 価格の数値化（複数回使うので最初に処理）
    p = int(item["price"].replace("円", "").replace(",", ""))

    # 価格帯による色分け（既存仕様を維持）
    color = (
        0xE74C3C if p <= 5000 else
        0x3498DB if p <= 9999 else
        0x2ECC71
    )

    # URL は短縮版を使用（既存仕様）
    short = get_short_url(item["url"])

    # embed のフィールド
    fields = [
        {"name": "URL", "value": short, "inline": False},
        {
            "name": "販売形式",
            "value": "既存販売" if item["mode"] == "exist" else "オークション",
            "inline": True,
        },
        {"name": "価格", "value": item["price"], "inline": True},
    ]

    # 即決価格がある場合のみ追加（既存仕様）
    if item["buy_now"]:
        fields.append({
            "name": "即決価格",
            "value": item["buy_now"],
            "inline": True
        })

    # embed 本体
    embed = {
        "title": item["title"][:256],  # Discord の制限に合わせる
        "url": short,
        "color": color,
        "fields": fields,
        "seller": seller,  # ← 重要：seller を embed に保持
    }

    # サムネイル画像（存在する場合のみ）
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

    try:
        # ============================
        # 朝6:00 → 深夜帯まとめ通知
        # ============================
        if is_morning():
            pending = (
                load_json(DATA_PENDING_EXIST, []) +
                load_json(DATA_PENDING_AUCTION, [])
            )
            if pending:
                send_discord(WEBHOOK_URL, "🌅 深夜帯まとめ通知", pending[:10])

            clear_json(DATA_PENDING_EXIST)
            clear_json(DATA_PENDING_AUCTION)

        # ============================
        # 商品一覧取得
        # ============================
        soup_exist = parse_html(fetch_html(URL_EXIST))
        soup_auction = parse_html(fetch_html(URL_AUCTION))

        items = []
        if soup_exist:
            items += parse_items(soup_exist, "exist")
        if soup_auction:
            items += parse_items(soup_auction, "auction")

        # 価格の安い順に並べる（既存仕様）
        items.sort(key=lambda x: int(x["price"].replace("円", "").replace(",", "")))

        embeds = []

        # ============================
        # 商品ごとの処理
        # ============================
        for item in items:
            key = normalize_url(item["url"])
            h = generate_item_hash(key)

            # すでに通知済みならスキップ
            if h in last:
                continue

            # 価格の数値化（複数回使うので最初に）
            price = int(item["price"].replace("円", "").replace(",", ""))

            # seller_id を取得（キャッシュあり）
            seller = fetch_seller_id(item["url"])

            # ============================
            # special_users → 最優先で通知
            # ============================
            if seller in SPECIAL_USERS:
                if len(embeds) < 10:
                    embeds.append(build_embed(item, seller))
                last[h] = True
                continue

            # ============================
            # 通常の価格フィルタ（15000円以上は通知しない）
            # ============================
            if price >= 15000:
                last[h] = True
                continue

            # ============================
            # 除外ユーザー
            # ============================
            if not seller or seller in EXCLUDE_USERS:
                last[h] = True
                continue

            # ============================
            # 深夜帯 → pending に保存
            # ============================
            if is_night():
                path = DATA_PENDING_EXIST if item["mode"] == "exist" else DATA_PENDING_AUCTION
                append_json_list(path, item)
                last[h] = True
                continue

            # ============================
            # 通常通知
            # ============================
            if len(embeds) < 10:
                embeds.append(build_embed(item, seller))

            last[h] = True

        # ============================
        # 通知送信
        # ============================
        if embeds:
            # special_users が含まれているか判定（embed に seller を保持している）
            contains_special = any(
                embed.get("seller") in SPECIAL_USERS
                for embed in embeds
            )

            if contains_special:
                # @everyone は優先通知のときだけ
                title = "@everyone\n💌つなぐ　優先通知"
            else:
                first_price = int(
                    embeds[0]["fields"][2]["value"].replace("円", "").replace(",", "")
                )
                title = (
                    "📢つなぐ　新着通知" if first_price <= 5000 else
                    "🔔つなぐ　新着通知" if first_price <= 9999 else
                    "📝つなぐ　新着通知"
                )

            send_discord(WEBHOOK_URL, title, embeds)

    finally:
        # 保存順序を seller_cache → last にして安全性UP
        save_json(DATA_SELLER, seller_cache)
        save_json(DATA_LAST, last)


# ============================
# エントリーポイント
# ============================

if __name__ == "__main__":
    main()
