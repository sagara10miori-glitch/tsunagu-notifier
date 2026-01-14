import hashlib

from utils.storage import load_json, save_json

DATA_SHORT = "data/short_cache.json"


def _h(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]


def get_short_url(url):
    cache = load_json(DATA_SHORT, {})
    if url in cache:
        return cache[url]

    short = f"{url}#s={_h(url)}"
    cache[url] = short

    if len(cache) > 500:
        cache = dict(list(cache.items())[-500:])

    save_json(DATA_SHORT, cache)
    return short
