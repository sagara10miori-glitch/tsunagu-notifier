import hashlib

def generate_item_hash(title, author, url):
    base = f"{title}|{author}|{url}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()
