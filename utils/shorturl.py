import requests

def get_short_url(url):
    try:
        r = requests.get("https://is.gd/create.php", params={"format": "simple", "url": url}, timeout=5)
        if r.status_code == 200:
            return r.text.strip()
    except:
        pass
    return url
