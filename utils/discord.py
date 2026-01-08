import requests
import time

MAX_EMBEDS = 10  # Discord の 10 embeds 制限
TIMEOUT = 10
RETRY = 3


def validate_embed(embed):
    """
    Discord の仕様に合わせて embed を安全に整形する。
    """
    if "title" in embed and embed["title"] is None:
        embed["title"] = ""

    if "description" in embed and embed["description"] is None:
        embed["description"] = ""

    # Discord の文字数制限対策（過剰な長文を防ぐ）
    if "description" in embed and len(embed["description"]) > 4000:
        embed["description"] = embed["description"][:3990] + "…"

    return embed


def send_discord(webhook_url, content=None, embeds=None):
    """
    Discord Webhook に送信する。
    - embeds は最大 10 個まで
    - リトライ 3 回
    - 失敗してもシステムを止めない
    """

    if embeds is None:
        embeds = []

    # Discord の embed 制限に合わせる
    embeds = embeds[:MAX_EMBEDS]
    embeds = [validate_embed(e) for e in embeds]

    payload = {
        "content": content or "",
        "embeds": embeds
    }

    for i in range(RETRY):
        try:
            res = requests.post(
                webhook_url,
                json=payload,
                timeout=TIMEOUT
            )

            if res.status_code in (200, 204):
                return True

            print(f"[WARNING] Discord HTTP {res.status_code}")
            time.sleep(1)

        except Exception as e:
            print(f"[WARNING] Discord send failed ({i+1}/{RETRY})")
            print(e)
            time.sleep(1)

    print("[ERROR] Failed to send Discord message")
    return False
