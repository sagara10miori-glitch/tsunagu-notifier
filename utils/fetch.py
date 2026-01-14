from bs4 import BeautifulSoup

def parse_html(html: str):
    return BeautifulSoup(html, "html.parser") if html else None

def validate_image_url(url: str):
    return url if url and url.startswith(("http://", "https://")) else None
