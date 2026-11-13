import re
from typing import Any, Dict, List

from crewai.tools import BaseTool
from crewai_tools import SerperDevTool
from pydantic import PrivateAttr


class PhoneSearchTool(BaseTool):
    """Serper-based search tool that filters URLs to the target domain.

    Wraps SerperDevTool, caps results at max_urls, and returns only
    URLs belonging to the target retailer domain.
    """

    name: str = "phone_search_tool"
    description: str = (
        "Search for phone product pages on a given retailer domain "
        "using Serper, filtered and capped by max_urls."
    )
    target_domain: str
    max_urls: int = 25

    _serper: Any = PrivateAttr()

    def __init__(self, target_domain: str, max_urls: int = 25) -> None:
        super().__init__(target_domain=target_domain, max_urls=max_urls)
        self._serper = SerperDevTool()

    def _run(self, query: str) -> Dict[str, List[str]]:
        raw_results = self._serper._run(query=query)
        # Serper returns a string or dict depending on version; normalize to list
        urls: List[str] = []
        if isinstance(raw_results, str):
            urls = re.findall(
                r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                raw_results,
            )
        elif isinstance(raw_results, dict):
            urls = raw_results.get("urls", []) or []

        # Filter to target domain and cap at max_urls
        filtered = [u for u in urls if self.target_domain in u][: self.max_urls]

        return {"urls": filtered}
