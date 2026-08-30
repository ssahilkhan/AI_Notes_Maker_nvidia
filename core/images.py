import base64
import re
from urllib.parse import quote

import requests

API_URL = "https://commons.wikimedia.org/w/api.php"


def mermaid_img_url(code):
    encoded = quote(base64.urlsafe_b64encode(code.encode("utf-8")).decode("utf-8"))
    return f"https://mermaid.ink/img/{encoded}"


def search_images(query, limit=8):
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size|mime",
        "iiurlwidth": 480,
        "format": "json",
        "origin": "*",
    }
    try:
        resp = requests.get(API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []
    pages = (data.get("query") or {}).get("pages") or {}
    results = []
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        if not is_image_mime(info.get("mime", "")):
            continue
        meta = info.get("extmetadata") or {}
        artist_raw = (meta.get("Artist") or {}).get("value", "") or ""
        license_raw = (meta.get("LicenseShortName") or {}).get("value", "") or ""
        desc_raw = (meta.get("ImageDescription") or {}).get("value", "") or ""
        url = info.get("descriptionurl") or ""
        results.append(
            {
                "thumburl": info.get("thumburl") or "",
                "fullurl": info.get("url") or "",
                "page": url,
                "title": page.get("title", ""),
                "artist": strip_html(artist_raw)[:120],
                "license": strip_html(license_raw)[:80],
                "description": strip_html(desc_raw)[:160],
                "width": info.get("width"),
                "height": info.get("height"),
            }
        )
    return results


def is_image_mime(mime):
    return mime.startswith("image/") and mime not in ("image/svg+xml", "image/x-icon")


def strip_html(text):
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_image_bytes(url, timeout=20):
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content