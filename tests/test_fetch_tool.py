import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace
from typing import Any, Tuple
from unittest.mock import patch

import pytest

from phone_agent.tools.cache import PageCache
from phone_agent.tools.fetch_tool import PlaywrightFetchTool


class _QuietHandler(BaseHTTPRequestHandler):
    """Serve static files from the repository root."""

    def log_message(self, format: str, *args: Any) -> None:  # silence stderr
        pass

    def do_GET(self) -> None:
        path = self.path.lstrip("/")
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture
def httpserver() -> Any:
    """Start a stdlib HTTP server on a random port serving fixture pages."""
    server = HTTPServer(("127.0.0.1", 0), _QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    yield port, server
    server.shutdown()


def _tool(cache_dir: Any) -> PlaywrightFetchTool:
    settings = SimpleNamespace(
        headless=True,
        cache_dir=cache_dir,
        fetch_timeout_ms=60000,
        max_fetch_retries=1,
    )
    return PlaywrightFetchTool(settings)


def test_fetch_tool_cache_hit(httpserver: Tuple[int, Any], tmp_path: Any) -> None:
    """Fetch tool: first call goes to browser, second hits cache."""
    port, _server = httpserver
    url = f"http://localhost:{port}/tests/fixtures/pages/iphone.html"
    tool = _tool(tmp_path / ".cache")

    with patch("phone_agent.tools.fetch_tool.sync_playwright") as mock_pw:
        mock_instance = mock_pw.return_value.__enter__.return_value
        mock_browser = mock_instance.chromium.launch.return_value
        mock_page = mock_browser.new_page.return_value
        mock_page.inner_text.return_value = "iPhone 15 Pro 8 GB 256 GB"

        result1 = tool._run(url)
        assert "iPhone" in result1
        assert mock_page.inner_text.call_count == 1

        result2 = tool._run(url)
        assert "iPhone" in result2
        assert mock_page.inner_text.call_count == 1


def test_fetch_tool_markdown_strips_script(
    httpserver: Tuple[int, Any], tmp_path: Any
) -> None:
    """Fetch returned Markdown contains the phone name and excludes script text."""
    port, _server = httpserver
    url = f"http://localhost:{port}/tests/fixtures/pages/iphone.html"
    tool = _tool(tmp_path / ".cache")

    with patch("phone_agent.tools.fetch_tool.sync_playwright") as mock_pw:
        mock_instance = mock_pw.return_value.__enter__.return_value
        mock_browser = mock_instance.chromium.launch.return_value
        mock_page = mock_browser.new_page.return_value

        body = (
            '<nav><a href="/">Home</a></nav>'
            "<footer><p>© 2024 Apple</p></footer>"
            "<header><h1>iPhone 15 Pro</h1></header>"
            "<article><dl><dt>Chipset</dt><dd>Apple A17 Pro</dd></dl>"
            '<script>console.log("tracking");</script>'
            "<style>.hidden { display: none; }</style>"
            "</article>"
        )
        mock_page.inner_text.return_value = body

        result = tool._run(url)

        assert "iPhone 15 Pro" in result
        assert "console.log" not in result
        assert "<script>" not in result


def test_fetch_tool_cache_second_call_not_called(
    httpserver: Tuple[int, Any], tmp_path: Any
) -> None:
    """Second call to fetch tool hits cache and never launches Chromium."""
    port, _server = httpserver
    url = f"http://localhost:{port}/tests/fixtures/pages/iphone.html"
    tool = _tool(tmp_path / ".cache")

    with patch("phone_agent.tools.fetch_tool.sync_playwright") as mock_pw:
        mock_instance = mock_pw.return_value.__enter__.return_value
        mock_browser = mock_instance.chromium.launch.return_value
        mock_page = mock_browser.new_page.return_value
        mock_page.inner_text.return_value = "iPhone 15 Pro"

        _ = tool._run(url)
        mock_page.inner_text.reset_mock()

        result2 = tool._run(url)
        assert mock_page.inner_text.call_count == 0
        assert "iPhone" in result2


def test_page_cache_roundtrip(tmp_path: Any) -> None:
    cache = PageCache(str(tmp_path / "cache"))
    assert cache.get("http://example.com/phone") is None
    cache.put("http://example.com/phone", "# Phone")
    assert cache.get("http://example.com/phone") == "# Phone"
