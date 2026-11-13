from crewai import Task

from phone_agent.agents import extractor, fetcher, reporter, scout, validator
from phone_agent.schemas import PhoneList, RawPageList, UrlList, ValidatedPhones


# ── Task 1: URL Discovery ──────────────────────────────────────────────
task_discover_urls = Task(
    description=(
        "Given a retailer base URL, discover phone product pages "
        "using the PhoneSearchTool. Cap results at {max_urls} URLs. "
        "Return a UrlList wrapper."
    ),
    expected_output="UrlList containing discovered product page URLs",
    output_pydantic=UrlList,
    agent=scout,
    context=[],
)

# ── Task 2: Fetch Pages ────────────────────────────────────────────────
task_fetch_pages = Task(
    description=(
        "Fetch each URL from the UrlList using PlaywrightFetchTool "
        "with disk cache. Skip already-cached URLs. Return a "
        "RawPageList mapping URL -> markdown content."
    ),
    expected_output="RawPageList of URL -> markdown mappings",
    output_pydantic=RawPageList,
    agent=fetcher,
    context=[task_discover_urls],
)

# ── Task 3: Extract Specs ──────────────────────────────────────────────
task_extract_specs = Task(
    description=(
        "Extract structured phone specifications (name, brand, price, "
        "currency, chipset, ram_gb, storage_gb, screen_size_inch, "
        "battery_mah, camera_mp, os, source_url) from each raw page "
        "markdown. Return a PhoneList wrapper."
    ),
    expected_output="PhoneList of extracted PhoneSpec records",
    output_pydantic=PhoneList,
    agent=extractor,
    context=[task_fetch_pages],
)

# ── Task 4: Validate Records ───────────────────────────────────────────
task_validate = Task(
    description=(
        "Validate all extracted phone records using deterministic "
        "rules: EMPTY_NAME, NO_SOURCE, BAD_PRICE, BAD_RAM, BAD_STORAGE, "
        "BAD_SCREEN, BAD_BATTERY, BAD_CAMERA, DUP_URL_NAME. Each rejection "
        "recorded as {\"record\": ..., \"reason\": \"<code>\"}. Return a "
        "ValidatedPhones wrapper."
    ),
    expected_output="ValidatedPhones with valid records and/or rejections",
    output_pydantic=ValidatedPhones,
    agent=validator,
    context=[task_extract_specs],
)

# ── Task 5: Report / Export ─────────────────────────────────────────────
task_report = Task(
    description=(
        "Write the validated phone records to phones.csv and "
        "phones.xlsx in the configured out_dir. Also write "
        "out/rejected.json if any records were rejected. Print "
        "final counts line: {found, fetched, extracted, valid, rejected}."
    ),
    expected_output="CSV and Excel files written; counts printed to stderr",
    output_pydantic=None,  # reporter has no Pydantic output
    agent=reporter,
    context=[task_validate],
)
