import requests
import json

def send_discord(webhook_url, content=None, embeds=None):
    payload = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    headers = {"Content-Type": "application/json"}

    r = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
    r.raise_for_status()
