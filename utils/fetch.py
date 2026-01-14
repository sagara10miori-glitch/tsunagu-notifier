from bs4 import BeautifulSoup

def parse_html(html: str):
    if not html:
        return None
    return BeautifulSoup(html, "html.parser")


def validate_image_url(url: str) -> str | None:
    # HEAD リクエストは重いので行わない
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return None
