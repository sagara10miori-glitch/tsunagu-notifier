import hashlib

def generate_item_hash(s: str):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
