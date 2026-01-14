import requests
from typing import Any

def send_discord(webhook_url: str, content: str | None = None, embeds: list[dict] | None = None):
    if not webhook_url:
        return

    payload: dict[str, Any] = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    headers = {"Content-Type": "application/json"}

    try:
        requests.post(webhook_url, json=payload, headers=headers, timeout=5)
    except Exception:
        pass
