from crewai import LLM, Agent

from phone_agent.config import settings


def _make_agent(role: str, goal: str, backstory: str) -> Agent:
    """Factory for all agents — same model config across the pipeline."""
    return Agent(
        role=role,
        goal=goal,
        backstory=backstory,
        llm=LLM(model=settings.model, temperature=0.1),
        allow_delegation=False,
        verbose=True,
        max_iter=8,
    )


# ── Agent instances (import-time: tools list is empty) ──────────────────

scout = _make_agent(
    role="Phone Product URL Scout",
    goal="Discover paginated phone product pages on the target retailer site.",
    backstory=(
        "A meticulous researcher who understands retailer pagination and "
        "only reports URLs that belong to the target domain."
    ),
)
"""URL discovery agent — pagination-aware, uses PhoneSearchTool"""

fetcher = _make_agent(
    role="Phone Page Fetcher",
    goal="Render each product page and return clean, honest page content.",
    backstory=(
        "An adversarial fetcher who reports failures honestly instead of "
        "inventing page content."
    ),
)
"""Fetch agent — headless Playwright render, honest error reporting"""

extractor = _make_agent(
    role="Phone Spec Extractor",
    goal="Extract structured phone specifications from raw page markdown.",
    backstory=(
        "A precise extractor who prefers nulls over guesses and never "
        "invents a specification that is not on the page."
    ),
)
"""Extraction agent — maps raw markdown to PhoneSpec records"""

validator = _make_agent(
    role="Phone Spec Validator",
    goal="Apply deterministic validation rules to extracted phone records.",
    backstory=(
        "A deterministic gatekeeper who calls validate_records() and never "
        "invents rules of their own."
    ),
)
"""Validation agent — deterministic gatekeeper, calls validate_records()"""

reporter = _make_agent(
    role="Phone Report Writer",
    goal="Write phones.csv and phones.xlsx and print the final counts.",
    backstory=(
        "A dependable reporter who writes files and prints accurate counts "
        "without embellishment."
    ),
)
"""Reporter agent — writes phones.csv + phones.xlsx, prints counts"""
