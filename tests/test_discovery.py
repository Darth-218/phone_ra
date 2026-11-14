from pathlib import Path
from types import SimpleNamespace
from typing import Any

import phone_agent.discovery as discovery
from phone_agent.discovery import (
    _extract_links,
    _filter_urls,
    _normalize_url,
    _parse_sitemap,
    _sitemap_candidates,
    discover_urls,
)

BASE = "https://www.example.com"


def _settings() -> Any:
    return SimpleNamespace(fetch_timeout_ms=1000)


def test_normalize_url_strips_fragment_and_tracking_params() -> None:
    url = "https://www.example.com/phones/iphone-15?utm_source=ad&color=black#specs"
    assert _normalize_url(url) == (
        "https://www.example.com/phones/iphone-15?color=black"
    )


def test_normalize_url_rejects_non_http() -> None:
    assert _normalize_url("mailto:sales@example.com") is None
    assert _normalize_url("/relative/path", BASE) == "https://www.example.com/relative/path"


def test_filter_urls_keeps_same_site_products_and_dedupes() -> None:
    urls = [
        "https://www.example.com/phones/iphone-15",
        "https://www.example.com/phones/iphone-15#specs",
        "https://www.example.com/smartphones/galaxy-s24",
        "https://www.example.com/cart",
        "https://www.example.com/blog/best-phones",
        "https://www.example.com/support/warranty",
        "https://www.example.com/headphones/airpods",
        "https://external.example.com/phones/iphone-15",
    ]

    assert _filter_urls(urls, BASE, 10) == [
        "https://www.example.com/phones/iphone-15",
        "https://www.example.com/smartphones/galaxy-s24",
    ]


def test_filter_urls_caps_results() -> None:
    urls = [f"https://www.example.com/phones/model-{i}" for i in range(10)]
    assert len(_filter_urls(urls, BASE, 3)) == 3


def test_parse_sitemap_urlset() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://www.example.com/phones/iphone-15</loc></url>
      <url><loc>https://www.example.com/phones/pixel-8</loc></url>
    </urlset>
    """

    pages, children = _parse_sitemap(xml)

    assert pages == [
        "https://www.example.com/phones/iphone-15",
        "https://www.example.com/phones/pixel-8",
    ]
    assert children == []


def test_parse_sitemap_index() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://www.example.com/sitemap-phones.xml</loc></sitemap>
      <sitemap><loc>https://www.example.com/sitemap-tablets.xml</loc></sitemap>
    </sitemapindex>
    """

    pages, children = _parse_sitemap(xml)

    assert pages == []
    assert children == [
        "https://www.example.com/sitemap-phones.xml",
        "https://www.example.com/sitemap-tablets.xml",
    ]


def test_parse_sitemap_invalid_xml_returns_empty() -> None:
    assert _parse_sitemap("not xml") == ([], [])


def test_extract_links_from_fixture() -> None:
    fixture = (
        Path(__file__).parent / "fixtures" / "pages" / "listing.html"
    ).read_text(encoding="utf-8")

    links = _extract_links(fixture, f"{BASE}/tests/fixtures/pages/listing.html")

    assert f"{BASE}/tests/fixtures/pages/iphone.html" in links
    assert f"{BASE}/tests/fixtures/pages/pixel-8.html?utm_source=ad" in links
    assert "https://external.example.com/phone" in links


def test_sitemap_candidates_reads_robots(monkeypatch: Any) -> None:
    def fake_fetch(url: str, timeout_s: int) -> str:
        assert url == f"{BASE}/robots.txt"
        return "User-agent: *\nSitemap: https://www.example.com/sitemap-phones.xml\n"

    monkeypatch.setattr(discovery, "_fetch_text", fake_fetch)

    assert _sitemap_candidates(BASE, 5) == [
        "https://www.example.com/sitemap-phones.xml",
        "https://www.example.com/sitemap.xml",
    ]


def test_discover_urls_uses_sitemap_results(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        discovery,
        "_discover_from_sitemaps",
        lambda *args: ["https://www.example.com/phones/iphone-15"],
    )
    monkeypatch.setattr(discovery, "_crawl_links", lambda *args: [])

    assert discover_urls(BASE, 5, _settings()) == [
        "https://www.example.com/phones/iphone-15"
    ]


def test_discover_urls_falls_back_to_supplied_url(monkeypatch: Any) -> None:
    monkeypatch.setattr(discovery, "_discover_from_sitemaps", lambda *args: [])
    monkeypatch.setattr(discovery, "_crawl_links", lambda *args: [])

    assert discover_urls(BASE, 5, _settings()) == [f"{BASE}/"]
