import os
import hashlib
from utils.storage import load_json, save_json

DATA_SHORT_CACHE = "data/short_cache.json"

def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]

def get_short_url(url: str) -> str:
    cache = load_json(DATA_SHORT_CACHE, default={})
    if url in cache:
        return cache[url]

    # 実際の短縮サービスを使わず、ハッシュで短縮風URLを作る
    short = f"{url}#s={_hash_url(url)}"

    cache[url] = short
    if len(cache) > 1000:
        cache = dict(list(cache.items())[-500:])
    save_json(DATA_SHORT_CACHE, cache)

    return short
