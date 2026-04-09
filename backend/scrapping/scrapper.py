#!/usr/bin/env python3
import os
import re
import io
import gzip
import time
import hashlib
import logging
import typing as t
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests

# -------------------------
# CONFIG
# -------------------------
SITEMAP_INDEX = "https://www.pointp.fr/sitemap_index.xml"
BASE_NETLOC = "www.pointp.fr"
SAVE_ROOT = "pages_pointp"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36")
REQUEST_TIMEOUT = 20
DELAY_SECONDS = 1.0           # politeness delay
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0           # seconds

# Optional: if you only want product/category/cms sitemaps etc., you can filter by sitemap name here
SITEMAP_ALLOW_SUBSTRINGS: t.List[str] = []  # e.g. ["page", "product", "category"] to narrow scope

# -------------------------
# ROBOTS FILTERS (derived from robots.txt)
# We use a conservative subset to avoid fetching disallowed stuff.
# -------------------------
DISALLOW_REGEXES = [
    r"/core/.*",
    r"/profiles/.*",

    # clean URL paths
    r"/admin/.*",
    r"/comment/reply/.*",
    r"/filter/tips",
    r"/node/add/.*",
    r"/search.*",
    r"/user/(register|password|login|logout)/.*",

    # no clean URLs
    r"/node/.*",
    r"/index\.php/(admin|comment/reply|filter/tips|node/add|search|user/(password|register|login|logout)).*",

    # explicit disallows (selection)
    r"/filtre/.*",
    r"/html/.*",
    r"/spip.*",
    r"/agences/jsp/.*",
    r"/connexion\?.*",
    r"/footer/.*",
    r"/footer-.*",
    r"/promotions-agence\?.*",
    r"/recherche\?.*",
    r"/app/(perso|metiers|article/notification)/.*",
    r"/les-marques\?category=.*",
    r"/les-marques/.*\?filters=f/.*",
    r"/les-marques/.*\?c=.*",

    # file types & patterns
    r".*\.pdf($|\?)",
    r".*\.jsp($|\?)",
    r".*\.srvl($|\?)",

    # parameters to avoid
    r".*srsltid.*",
    r".*utm_.*",
    r".*gclid.*",
    r".*\?page=.*",
    r".*\?sort(_by|_order)?=.*",
    r".*\?category=.*",
    r".*\?id_produit=.*",
    r".*\?field_conseils_themes_target.*",
]

disallow_compiled = [re.compile(pat, re.IGNORECASE) for pat in DISALLOW_REGEXES]

def is_allowed_url(url: str) -> bool:
    """Conservative robots filter."""
    p = urlparse(url)
    if p.netloc != BASE_NETLOC:
        return False
    path_query = p.path
    if p.query:
        path_query += "?" + p.query
    for rgx in disallow_compiled:
        if rgx.match(path_query):
            return False
    # Keep only HTML-like targets: no obvious file extensions other than .html
    # If the URL ends with a typical binary/web asset, skip it.
    if re.search(r"\.(pdf|jpg|jpeg|png|gif|svg|webp|css|js|ico|mp4|mp3|zip|gz)(\?|$)", p.path, re.IGNORECASE):
        return False
    return True

# -------------------------
# HTTP helpers
# -------------------------
session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

def http_get(url: str) -> requests.Response:
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r
        except Exception as e:
            last_err = e
            logging.warning("GET failed (%s) %s [attempt %d/%d]", type(e).__name__, url, attempt, MAX_RETRIES)
            time.sleep(RETRY_BACKOFF * attempt)
    raise RuntimeError(f"Failed to fetch {url}: {last_err}")

# -------------------------
# Sitemap parsing
# -------------------------
def iter_sitemaps_from_index(index_url: str) -> t.Iterable[str]:
    r = http_get(index_url)
    content = r.content
    if r.headers.get("Content-Type","").lower().endswith("gzip") or index_url.endswith(".gz"):
        content = gzip.decompress(content)

    root = ET.fromstring(content)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    # Many sitemap indices use <sitemap><loc>...</loc></sitemap>
    for sm_el in root.findall(".//sm:sitemap/sm:loc", ns):
        loc = sm_el.text.strip()
        if SITEMAP_ALLOW_SUBSTRINGS and not any(s in loc for s in SITEMAP_ALLOW_SUBSTRINGS):
            continue
        yield loc

def iter_urls_from_sitemap(smap_url: str) -> t.Iterable[str]:
    r = http_get(smap_url)
    content = r.content
    if r.headers.get("Content-Type","").lower().endswith("gzip") or smap_url.endswith(".gz"):
        try:
            content = gzip.decompress(content)
        except OSError:
            # some servers send gz content-type but it's plain xml
            pass
    root = ET.fromstring(content)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    for url_el in root.findall(".//sm:url/sm:loc", ns):
        loc = url_el.text.strip()
        yield loc

# -------------------------
# Saving
# -------------------------
def url_to_local_path(url: str) -> str:
    """Mirror path to disk; `.../foo/` -> .../foo/index.html; `.../bar.html` preserved."""
    p = urlparse(url)
    assert p.netloc == BASE_NETLOC
    # Normalize path
    path = p.path
    if path.endswith("/"):
        path = path + "index.html"
    elif not os.path.splitext(path)[1]:
        # no extension: assume HTML and add /index.html
        path = path.rstrip("/") + "/index.html"

    # Prepend domain directory
    local_path = os.path.join(SAVE_ROOT, p.netloc, path.lstrip("/"))
    # Ensure parent dir exists
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    return local_path

def already_saved_same(url: str, body: bytes) -> bool:
    """Deduplicate by hash file next to the html (optional)."""
    target = url_to_local_path(url)
    hash_now = hashlib.sha256(body).hexdigest()
    hash_path = target + ".sha256"
    if os.path.exists(hash_path):
        with open(hash_path, "r", encoding="utf-8") as f:
            if f.read().strip() == hash_now:
                return True
    with open(hash_path, "w", encoding="utf-8") as f:
        f.write(hash_now)
    return False

def save_html(url: str, resp: requests.Response) -> None:
    target = url_to_local_path(url)
    # Only save if content is HTML-ish
    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "text/html" not in ctype and "application/xhtml+xml" not in ctype:
        logging.info("Skip (not HTML): %s [%s]", url, ctype)
        return
    body = resp.content
    if already_saved_same(url, body):
        logging.info("Duplicate (hash match), skip save: %s", url)
        return
    with open(target, "wb") as f:
        f.write(body)
    logging.info("Saved: %s -> %s", url, target)

# -------------------------
# Main
# -------------------------
def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.info("Saving to %s", os.path.abspath(SAVE_ROOT))

    # Gather all sitemap URLs (index may contain many sitemap parts)
    sitemaps = list(iter_sitemaps_from_index(SITEMAP_INDEX))
    if not sitemaps:
        # some sites expose a single non-index sitemap directly
        sitemaps = [SITEMAP_INDEX]

    logging.info("Found %d sitemap files", len(sitemaps))

    seen: set[str] = set()
    kept: list[str] = []

    # Collect URLs from all sitemaps
    for sm in sitemaps:
        logging.info("Reading sitemap: %s", sm)
        for loc in iter_urls_from_sitemap(sm):
            if urlparse(loc).netloc != BASE_NETLOC:
                continue
            if loc in seen:
                continue
            seen.add(loc)
            if is_allowed_url(loc):
                kept.append(loc)

    logging.info("Collected %d URLs (kept after robots-style filters: %d)", len(seen), len(kept))

    # Fetch & save
    for i, url in enumerate(kept, 1):
        try:
            resp = http_get(url)
            save_html(url, resp)
        except Exception as e:
            logging.warning("Failed to save %s: %s", url, e)
        time.sleep(DELAY_SECONDS)

    logging.info("Done. Attempted %d HTML pages.", len(kept))

if __name__ == "__main__":
    main()