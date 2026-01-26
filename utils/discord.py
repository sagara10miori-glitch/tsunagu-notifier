import requests

def send_discord(url, title, embeds):
    payload = {
        "content": title,
        "embeds": embeds,
    }

    try:
        r = requests.post(url, json=payload, timeout=5)
        return r.status_code == 204 or r.status_code == 200
    except Exception:
        return False
