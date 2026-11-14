from __future__ import annotations

import gzip
import logging
import re
from typing import List, Optional, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from phone_agent.config import Settings

log = logging.getLogger("phone-agent.discovery")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

MAX_SITEMAPS = 10
MAX_COLLECTED = 5000
MAX_SITEMAP_DEPTH = 2

PRODUCT_PATTERN = re.compile(
    r"(phone|mobile|smartphone|cellphone|product|/p/|/dp/|/buy)",
    re.IGNORECASE,
)

EXCLUDE_PATTERN = re.compile(
    r"(?:^|/)("
    r"cart|basket|checkout|login|signin|sign-in|account|wishlist|compare|"
    r"search|blog|news|support|warranty|repair|trade-in|accessories|accessory|"
    r"case|cases|charger|chargers|cover|covers|screen-protector|deals|"
    r"privacy|terms|contact|about|headphone|headphones|earphone|earbud|earbuds"
    r")(?:/|$)",
    re.IGNORECASE,
)

MODEL_DIGITS_PATTERN = re.compile(r"/[^/]*\d+[^/]*/?$")

TRACKING_PARAMS = {
    "gclid",
    "fbclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_",
    "source",
}


def _normalize_url(url: str, base: Optional[str] = None) -> Optional[str]:
    """Resolve, canonicalize, and validate a URL."""
    if base:
        url = urljoin(base, url)
    url = url.strip()
    if not url:
        return None

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None

    netloc = parsed.netloc.lower()
    path = parsed.path or "/"

    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_")
            and key.lower() not in TRACKING_PARAMS
        ]
    )

    return urlunparse((parsed.scheme, netloc, path, "", query, ""))


def _same_site(url: str, base: str) -> bool:
    url_host = urlparse(url).netloc.lower()
    base_host = urlparse(base).netloc.lower()
    return url_host.removeprefix("www.") == base_host.removeprefix("www.")


def _looks_like_product(url: str) -> bool:
    path = urlparse(url).path
    if EXCLUDE_PATTERN.search(path):
        return False
    if PRODUCT_PATTERN.search(path):
        return True
    return bool(MODEL_DIGITS_PATTERN.search(path))


def _filter_urls(urls: List[str], base: str, max_urls: int) -> List[str]:
    """Keep same-site, product-like URLs; dedupe while preserving order."""
    filtered: List[str] = []
    seen: Set[str] = set()

    for raw in urls:
        normalized = _normalize_url(raw, base)
        if not normalized:
            continue
        if not _same_site(normalized, base):
            continue
        if not _looks_like_product(normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        filtered.append(normalized)
        if len(filtered) >= max_urls:
            break

    return filtered


def _parse_sitemap(xml_text: str) -> Tuple[List[str], List[str]]:
    """Parse a sitemap or sitemap index.

    Returns ``(page_urls, child_sitemaps)``.
    """
    pages: List[str] = []
    children: List[str] = []

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return pages, children

    def local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    for node in root:
        node_name = local_name(node.tag)
        loc = None
        for child in node:
            if local_name(child.tag) == "loc" and child.text:
                loc = child.text.strip()
                break

        if not loc:
            continue

        if node_name == "url":
            pages.append(loc)
        elif node_name == "sitemap":
            children.append(loc)

    return pages, children


def _fetch_text(url: str, timeout_s: int) -> Optional[str]:
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=timeout_s) as response:
            data = response.read()
            if url.endswith(".gz") or response.headers.get("Content-Encoding") == "gzip":
                try:
                    data = gzip.decompress(data)
                except OSError:
                    pass
            return data.decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - discovery is best-effort
        log.debug("Could not fetch %s: %s", url, exc)
        return None


def _sitemap_candidates(base: str, timeout_s: int) -> List[str]:
    candidates: List[str] = []

    robots_url = urljoin(base, "/robots.txt")
    robots = _fetch_text(robots_url, timeout_s)
    if robots:
        for line in robots.splitlines():
            if line.lower().startswith("sitemap:"):
                candidate = line.split(":", 1)[1].strip()
                if candidate:
                    candidates.append(candidate)

    candidates.append(urljoin(base, "/sitemap.xml"))

    unique: List[str] = []
    seen = set()
    for candidate in candidates:
        normalized = _normalize_url(candidate, base)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _discover_from_sitemaps(base: str, timeout_s: int, max_urls: int) -> List[str]:
    queue: List[Tuple[str, int]] = [
        (url, 0) for url in _sitemap_candidates(base, timeout_s)
    ]
    visited: Set[str] = set()
    pages: List[str] = []
    fetched = 0

    while queue and fetched < MAX_SITEMAPS and len(pages) < MAX_COLLECTED:
        sitemap_url, depth = queue.pop(0)
        if sitemap_url in visited:
            continue
        visited.add(sitemap_url)

        xml_text = _fetch_text(sitemap_url, timeout_s)
        fetched += 1
        if not xml_text:
            continue

        found_pages, children = _parse_sitemap(xml_text)
        pages.extend(found_pages)

        if depth < MAX_SITEMAP_DEPTH:
            for child in children:
                normalized = _normalize_url(child, base)
                if normalized and normalized not in visited:
                    queue.append((normalized, depth + 1))

        filtered = _filter_urls(pages, base, max_urls)
        if len(filtered) >= max_urls:
            break

    return pages


def _extract_links(html: str, base: str) -> List[str]:
    """Extract absolute link targets from static HTML."""
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        if isinstance(href, str) and href.strip():
            links.append(urljoin(base, href.strip()))
    return links


def _crawl_links(base: str, timeout_ms: int) -> List[str]:
    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(base, timeout=timeout_ms)
            hrefs = page.eval_on_selector_all(
                "a[href]",
                "elements => elements.map(element => element.href)",
            )
            return [href for href in hrefs if isinstance(href, str)]
    except Exception as exc:  # noqa: BLE001 - discovery is best-effort
        log.warning("Could not crawl %s: %s", base, exc)
        html = _fetch_text(base, max(1, timeout_ms // 1000))
        if html:
            return _extract_links(html, base)
        return []
    finally:
        if browser is not None:
            browser.close()


def discover_urls(site: str, max_urls: int, settings: Settings) -> List[str]:
    """Discover product URLs for a retailer without a search API key.

    Discovery is deterministic and best-effort:

    1. Read ``robots.txt`` for sitemap locations (falling back to
       ``/sitemap.xml``) and walk sitemap indexes.
    2. Crawl the supplied page with Playwright and collect same-site links.
    3. Keep product-like URLs, dedupe, and cap at ``max_urls``.
    4. Fall back to the supplied URL when nothing else is found.
    """
    base = site.strip()
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"

    if max_urls <= 0:
        max_urls = 1

    timeout_s = max(1, settings.fetch_timeout_ms // 1000)

    collected = _discover_from_sitemaps(base, timeout_s, max_urls)
    filtered = _filter_urls(collected, base, max_urls)

    if len(filtered) < max_urls:
        crawled = _crawl_links(base, settings.fetch_timeout_ms)
        filtered = _filter_urls(filtered + crawled, base, max_urls)

    if filtered:
        log.info("Discovered %d URL(s) for %s", len(filtered), base)
        return filtered

    fallback = _normalize_url(base) or base
    log.warning("No product URLs discovered for %s; using the supplied URL", base)
    return [fallback]
