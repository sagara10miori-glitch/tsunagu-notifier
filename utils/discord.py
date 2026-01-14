import requests

def send_discord(webhook, content=None, embeds=None):
    if not webhook:
        return
    payload = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds
    try:
        requests.post(webhook, json=payload, timeout=5)
    except Exception:
        pass
