from bs4 import BeautifulSoup
import requests

def parse_html(html: str):
    if not html:
        return None
    return BeautifulSoup(html, "html.parser")

def validate_image_url(url: str) -> str | None:
    if not url:
        return None
    # 画像URLとして最低限のバリデーションだけ行う（HEADは重いので避ける）
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return None
