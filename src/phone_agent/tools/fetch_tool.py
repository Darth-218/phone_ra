import time
from typing import Any, Optional

from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from markdownify import markdownify as to_markdown
from playwright.sync_api import sync_playwright

from phone_agent.tools.cache import PageCache

MAX_CHARS = 60_000
STRIP_TAGS = ["script", "style", "nav", "footer", "svg"]


class PlaywrightFetchTool(BaseTool):
    """Playwright-based fetch tool with disk cache and NixOS support.

    Contract:
    - Cache lookup happens BEFORE launching the browser.
    - If cached → return immediately, never launch Chromium.
    - Browser binary is provided via PLAYWRIGHT_BROWSERS_PATH on NixOS.
    - Never run playwright install.
    - Strip script/style/nav/footer/svg tags; convert to Markdown.
    - Truncate to 60k chars with [...truncated...].
    - Retry up to max_fetch_retries with exponential backoff.
    - finally: browser.close() on every path.
    """

    name: str = "playwright_fetch_tool"
    description: str = (
        "Fetch and render a phone product page using Playwright "
        "(headless Chromium on NixOS via PLAYWRIGHT_BROWSERS_PATH), "
        "strip boilerplate, convert to Markdown, and truncate if needed."
    )
    settings: Any
    cache: Any

    def __init__(self, settings: Any) -> None:
        super().__init__(
            settings=settings,
            cache=PageCache(str(settings.cache_dir)),
        )

    def _run(self, url: str) -> str:
        # Cache lookup first — if hit, return immediately
        cached = self.cache.get(url)
        if cached is not None:
            return cached

        retries = max(1, getattr(self.settings, "max_fetch_retries", 2))
        last_exc: Optional[Exception] = None

        for attempt in range(retries):
            try:
                markdown = self._fetch_once(url)
                self.cache.put(url, markdown)
                return markdown
            except Exception as exc:  # noqa: BLE001 - reported after retries
                last_exc = exc
                if attempt + 1 < retries:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"Failed to fetch {url}: {last_exc}") from last_exc

    def _fetch_once(self, url: str) -> str:
        browser = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.settings.headless)
                page = browser.new_page()
                page.goto(url, timeout=self.settings.fetch_timeout_ms)

                raw = page.inner_text("body")
                soup = BeautifulSoup(raw, "html.parser")
                for tag in STRIP_TAGS:
                    for element in soup.find_all(tag):
                        element.decompose()

                markdown = to_markdown(str(soup)).strip()
                markdown = f"# {url}\n\n{markdown}"

                if len(markdown) > MAX_CHARS:
                    markdown = markdown[:MAX_CHARS] + "[...truncated...]"

                return markdown
        finally:
            if browser is not None:
                browser.close()
