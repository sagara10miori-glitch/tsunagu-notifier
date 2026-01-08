import hashlib


def generate_item_hash(title, author, price, url):
    """
    商品の重複防止ハッシュを生成する。
    ID が変わっても同一商品を検出できるように、
    複数フィールドを組み合わせて SHA-256 を生成する。
    """

    # None 対策（空文字に変換）
    title = title or ""
    author = author or ""
    price = str(price) if price is not None else ""
    url = url or ""

    base = f"{title}|{author}|{price}|{url}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()
