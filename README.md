# CrewAI Phone Research Agent (NixOS Edition)

## Goal & Scope

Build a CLI Python application that, given a retailer base URL, discovers phone product pages, renders them, extracts structured specs, validates the records, and writes `phones.csv` + `phones.xlsx`.

**In scope:** deterministic sitemap + link-crawl URL discovery, 4-agent CrewAI sequential pipeline, headless Playwright fetching with disk cache, Pydantic contracts at every handoff, deterministic validation, CSV/Excel export, NixOS dev shell.

**Out of scope:** web UI, database, scheduling, multi-retailer parallel execution, price history, image downloads.

**Target platform:** NixOS (dev + CI). Code remains portable to non-Nix systems, but the primary supported path is `nix-shell`.

---

## Repository Layout

```
phone-agent/
├── shell.nix                  # NixOS dev environment (mandatory)
├── .envrc                     # optional direnv (use nix)
├── pyproject.toml
├── .env.example
├── retailers.example.txt      # sample input file (one retailer link per line)
├── README.md
├── USAGE.md                   # full usage and options reference
├── src/phone_agent/
│   ├── __init__.py
│   ├── __main__.py            # CLI entrypoint
│   ├── config.py              # env + settings + startup checks
│   ├── sources.py             # retailer links input file loader
│   ├── discovery.py           # sitemap + link-crawl URL discovery
│   ├── schemas.py             # ALL Pydantic models (single source of truth)
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── fetch_tool.py      # Playwright + cache
│   │   └── cache.py
│   ├── agents.py
│   ├── tasks.py
│   ├── crew.py
│   ├── validate.py
│   └── export.py
├── tests/
│   ├── fixtures/
│   │   ├── pages/
│   │   └── expected/phones.json
│   ├── test_schemas.py
│   ├── test_fetch_tool.py
│   ├── test_export.py
│   ├── test_validate.py
│   ├── test_sources.py
│   └── test_pipeline_local.py
└── out/                       # gitignored
```

**Rule:** `schemas.py` is imported by every module. Never redefine a model elsewhere.

---

## 3. NixOS Development Environment

### 3.1 shell.nix (commit this file verbatim)

The `shell.nix` creates a development environment that:

- Installs Python 3.11, pip, and virtualenv
- Installs `playwright-driver` browsers (Chromium + ffmpeg, patched for NixOS)
- Sets `PLAYWRIGHT_BROWSERS_PATH` to the nix store path
- Sets `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` to avoid downloading browsers
- Creates and activates a venv on entry
- Warns if `pyproject.toml` playwright pin doesn't match nixpkgs

**Never run `playwright install` on NixOS.** The shell hook sets `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`; if you see a message asking you to run `playwright install`, that means the version pin is wrong or the shell was not entered.

```nix
{ pkgs ? import <nixpkgs> { } }:

let
  python = pkgs.python311;
  playwrightDriver = pkgs.playwright-driver;
in
pkgs.mkShell {
  name = "phone-agent-dev";

  packages = [
    python
    python.pkgs.pip
    python.pkgs.virtualenv
    playwrightDriver.browsers      # Chromium + ffmpeg, patched for NixOS
    pkgs.git
    pkgs.jq                        # for the version check in shellHook
  ];

  shellHook = ''
    # Use the nixpkgs-bundled Chromium instead of downloading one.
    export PLAYWRIGHT_BROWSERS_PATH=${playwrightDriver.browsers}
    export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true
    export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

    # Create / activate a venv on entry.
    if [ ! -d .venv ]; then
      ${python}/bin/python -m venv .venv
    fi
    source .venv/bin/activate
    export PATH="$PWD/.venv/bin:$PATH"

    # Sanity: warn if pyproject's playwright pin doesn't match nixpkgs.
    NIX_PW_VER="$(nix eval --raw nixpkgs#playwright-driver.version 2>/dev/null || echo '')"
    if [ -n "$NIX_PW_VER" ] && [ -f pyproject.toml ]; then
      PYPROJ_PW_VER="$(grep -oE 'playwright==[0-9.]+' pyproject.toml | head -1 | cut -d= -f3 || true)"
      if [ -n "$PYPROJ_PW_VER" ] && [ "$PYPROJ_PW_VER" != "$NIX_PW_VER" ]; then
        echo "WARNING: pyproject pins playwright==$PYPROJ_PW_VER, nixpkgs ships $NIX_PW_VER" >&2
        echo "         Align pyproject.toml before running the pipeline." >&2
      fi
    fi

    echo "phone-agent dev shell ready"
    echo "  PLAYWRIGHT_BROWSERS_PATH=$PLAYWRIGHT_BROWSERS_PATH"
    echo "  Next: pip install -e '.[dev]'"
  '';
}
```

### 3.2 .envrc (optional, for direnv users)

```bash
use nix
```

Add `use flake` alternative only if a `flake.nix` is later introduced. Do not add `layout python` — the shellHook already creates the venv.

### 3.3 Dependencies (`pyproject.toml`)

```toml
requires-python = ">=3.11"
dependencies = [
  "crewai>=0.86,<1.0",
  "crewai-tools>=0.30",
  "playwright==1.49.0",         # MUST match `nix eval nixpkgs#playwright-driver.version`
  "pydantic>=2.9",
  "pandas>=2.2",
  "openpyxl>=3.1",
  "python-dotenv>=1.0",
  "python-dotenv",
  "pydantic-settings>=2.5",
  "tenacity>=9.0",
  "beautifulsoup4>=4.12",
  "markdownify>=0.13",
]
[project.optional-dependencies]
dev = ["pytest>=8.3", "pytest-mock>=3.14", "ruff>=0.6", "mypy>=1.11"]
```

**The `playwright==…` pin is a hard requirement on NixOS.** If the build fails with a browser-version mismatch, the fix is to change this pin — never run `playwright install`.

### 3.4 Setup sequence (put in README verbatim)

```bash
nix-shell                       # enters shell, creates .venv, activates it
pip install -e '.[dev]'         # installs project + dev deps inside .venv
pytest                          # tests run against the nix-bundled Chromium
python -m phone_agent --site <url> --max-urls 5
```

**Do NOT run `playwright install` on NixOS.** The shell hook sets `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`; if you see a message asking you to run `playwright install`, that means the version pin is wrong or the shell was not entered.

### 3.5 .env.example

```bash
OPENAI_API_KEY=
PHONE_AGENT_MODEL=gpt-4o-mini
PHONE_AGENT_MAX_URLS=25
PHONE_AGENT_CACHE_DIR=.cache/pages
PHONE_AGENT_OUT_DIR=out
PHONE_AGENT_HEADLESS=true
PHONE_AGENT_FETCH_TIMEOUT_MS=60000
PHONE_AGENT_MAX_FETCH_RETRIES=2
```

---

## 4. Configuration (`config.py`)

```python
class Settings(BaseSettings):
    openai_api_key: str
    model: str = "gpt-4o-mini"
    max_urls: int = 25
    cache_dir: Path = Path(".cache/pages")
    out_dir: Path = Path("out")
    headless: bool = True
    fetch_timeout_ms: int = 60_000
    max_fetch_retries: int = 2
```

**Requirements:**

- Load from `.env` via `python-dotenv` (works fine inside `nix-shell`).
- **Fail fast** with a clear message if `OPENAI_API_KEY` is missing.
- Create `cache_dir` and `out_dir` if absent.
- **Startup assertion:** if `os.environ.get("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD") == "1"` but `PLAYWRIGHT_BROWSERS_PATH` is unset or points to a non-existent directory, raise `RuntimeError` with the message: `"You are on NixOS but not inside nix-shell. Run nix-shell and re-enter."`
- No other module reads `os.environ` directly.

---

## 5. Data Contracts (`schemas.py`)

**Key points repeated here for the coding agent:**

- All task outputs use wrapper models (`RawPageList`, `PhoneList`, `ValidatedPhones`). Never use bare `list[X]` in `output_pydantic`.
- `PhoneSpec` fields: `name`, `brand`, `price`, `currency`, `chipset`, `ram_gb`, `storage_gb`, `screen_size_inch`, `battery_mah`, `camera_mp`, `os`, `source_url`.
- **Currency validator uppercases input.**

---

## 6. Tools

### 6.1 `tools/cache.py`

`PageCache` with `key(url) -> sha256(url)[:16]`, `get(url) -> str | None`, `put(url, markdown) -> None`. Writes `{key}.md` and `{key}.meta.json`.

### 6.2 `discovery.py`

`discover_urls(site, max_urls, settings) -> list[str]`: no-key URL discovery.

- Reads `robots.txt` for sitemap locations (falling back to `/sitemap.xml`) and walks sitemap indexes.
- Crawls the supplied page with Playwright and extracts same-site `<a href>` links, with a static-HTML fallback.
- Keeps product-like URLs, drops cart/login/blog/accessory pages, dedupes, and caps at `max_urls`.
- Falls back to the supplied URL when nothing is discovered.

### 6.3 `tools/fetch_tool.py`

`PlaywrightFetchTool(BaseTool)`, contract unchanged from previous spec, plus:

- On NixOS the browser binary is provided by `pkgs.playwright-driver.browsers` via `PLAYWRIGHT_BROWSERS_PATH`. Do not pass `executable_path`; do not run `playwright install`.
- **Browser launch:**
  ```python
  from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
      browser = p.chromium.launch(headless=settings.headless)
      ...
      browser.close()
  ```
- **Cache lookup happens before launching the browser.** If cached → return immediately, never launch Chromium.
- **Same stripping rules:** drop `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, `<svg>`; convert to Markdown; truncate to 60k chars with `[...truncated...]`.
- **tenacity retry** (`stop_after_attempt(max_fetch_retries)`, exponential 2s→8s).
- **finally: `browser.close()`** on every path.

---

## 7. Agents (`agents.py`)

**Agent tools backstory theme**

| Agent | Tools | Backstory theme |
|-------|-------|----------------|
| fetcher | `PlaywrightFetchTool` | adversarial fetch, honest error reporting |
| extractor | none | nulls over guesses |
| validator | none | deterministic gatekeeper |
| reporter | none | writes files, prints counts |

**All agents:** `LLM(model=settings.model, temperature=0.1)`, `allow_delegation=False`, `verbose=True`, `max_iter=8`.

---

## 8. Tasks (`tasks.py`)

Four sequential tasks, with `context=[previous]` and `output_pydantic` on tasks 1–3. **Reporter task has no Pydantic output.** URL discovery runs deterministically before the crew and is passed in via the `{urls}` input.

---

## 9. Validation Rules (`validate.py`)

Deterministic Python. **Reject codes:** `EMPTY_NAME`, `NO_SOURCE`, `BAD_PRICE`, `BAD_RAM`, `BAD_STORAGE`, `BAD_SCREEN`, `BAD_BATTERY`, `BAD_CAMERA`, `DUP_URL_NAME`. Each rejection recorded as `{"record": ..., "reason": "<code>"}` in `ValidatedPhones.rejected`.

The **Validator agent** is instructed to call `validate_records()`; it does not invent rules.

---

## 10. Export (`export.py`)

`export_phones(records, out_dir) -> {"csv": path, "xlsx": path}`. Fixed column order, UTF-8 CSV, formatted Excel sheet `Phones` with frozen header and autofilter. Writes `out/rejected.json` if non-empty. **Raises `ValueError` on empty records.**

---

## 11. CLI (`__main__.py`)

```
python -m phone_agent --site <url> --max-urls 25 [--out-dir out] [--no-cache] [--dry-run]
python -m phone_agent --sites-file retailers.txt --max-urls 25 [--out-dir out]
```

`--sites-file` reads one retailer link per line. Blank lines and lines starting
with `#` are ignored, inline `#` comments are stripped, and duplicate links are
removed. When multiple links are provided, results are aggregated into a single
`phones.csv` / `phones.xlsx`. Use either `--site` or `--sites-file` (both may be
combined).

**Exit codes:** 0 success, 2 config error (including the NixOS shell check in §4), 3 zero valid records, 4 pipeline exception.

**Logging to stderr + out/run.log.** Final counts line: `{found, fetched, extracted, valid, rejected}`.

---

## 12. Build Order & Acceptance Criteria

### M0 — Skeleton
- Layout, `shell.nix`, `pyproject.toml`, `.envrc`, `.env.example`, `config.py`, `schemas.py`.
- ✅ `nix-shell` enters without error; `pip install -e '.[dev]'` succeeds; `pytest tests/test_schemas.py` passes.
- ✅ `python -c "import os; print(os.environ.get('PLAYWRIGHT_BROWSERS_PATH'))"` prints a valid nix store path.

### M1 — Tools & Discovery
- `cache.py`, `fetch_tool.py`, `discovery.py`.
- ✅ `test_fetch_tool.py` serves `tests/fixtures/pages/iphone.html` from a stdlib `http.server` on a random port; asserts returned Markdown contains "iPhone" and excludes `<script>` text; asserts second call hits cache (mock `sync_playwright` and assert not called).
- ✅ `test_discovery.py` covers sitemap parsing, robots.txt discovery, URL filtering/dedupe/cap, and fallback.
- ✅ Runs against the nix-bundled Chromium — no `playwright install` in CI. If the test fails with "browser not found", the coding agent must fix the playwright pin in `pyproject.toml`, not add an install step.
- ✅ No orphan Chromium processes after the test run.

### M2 — Agents & Tasks
- Import-time smoke test; assert `extractor.tools == []`, `validator.tools == []`.

### M3 — Crew + CLI (dry run)
- `python -m phone_agent --site <fixture server> --dry-run` exits 0 with no third-party network calls.

### M4 — Validation + Export
- `test_validate.py` and `test_export.py` cover every reject code from §9.

### M5 — Integration
- Static fixture server + mocked LLM. Full crew runs; `out/phones.csv` has expected rows; `out/run.log` contains the counts line.

### M6 — Live smoke test (manual, documented in README)
- Run once against a real retailer with `--max-urls 5`. Record in README's "Known limitations."

---

## 13. Guardrails

1. No bare `list[X]` in `output_pydantic`.
2. `max_iter=8` on every agent.
3. Truncate Markdown to 60k chars; log char count per page.
4. Cache keyed by URL; `--no-cache` bypasses.
5. Fail closed on empty validated set (exit 3, no CSV).
6. Redact `sk-…`/API-key patterns in the logger formatter.
7. **finally: `browser.close()`** on every Playwright path.
8. Determinism: temperature=0.1, `Process.sequential`, `memory=False`.
9. **NixOS: never invoke `playwright install`** anywhere in code, tests, CI, or README.

---

## 14. Definition of Done

- ✅ `shell.nix` committed and `nix-shell` enters cleanly, with `PLAYWRIGHT_BROWSERS_PATH` set to a nix store path.
- ✅ `pip install -e '.[dev]'` succeeds inside the shell's venv.
- ✅ `pytest` green (M0–M5), no live network, no `playwright install`.
- ✅ `ruff` check and `mypy --strict` clean on `src/`.
- ✅ `python -m phone_agent --help` documents every flag.
- ✅ README contains: NixOS setup (with the exact four commands from §3.4), the "Do NOT run `playwright install`" warning, env vars, CLI examples, M6 live-test notes, and "Known limitations" naming bot detection, JS-heavy sites, per-run LLM cost, and the playwright-pin alignment requirement.
- ✅ `examples/phones.example.csv` committed, generated from local fixtures.

---

## Two notes to pass along with the spec

**First:** tell the coding agent to write `shell.nix` and verify `nix-shell` enters before writing any Python. The whole pipeline depends on that shell hook exporting `PLAYWRIGHT_BROWSERS_PATH` and `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`; discovering the environment is broken at M1 costs far more than catching it at M0.

**Second:** when the coding agent hits a playwright version mismatch at M1 (and it likely will, since nixpkgs channels lag the pip release train), the correct fix is to `nix eval nixpkgs#playwright-driver.version` and pin `pyproject.toml` to that exact value. Installing the pip package's own browser download is not a valid workaround on NixOS and must not be added "just to unblock the test."

---

## Usage

See [USAGE.md](USAGE.md) for the complete reference: every CLI option, environment
variable, input file format, output file, exit code, validation rule, and
troubleshooting step.

Non-Nix users (Linux, macOS, Windows): see
[USAGE.md §2.2](USAGE.md#22-non-nix-systems-linux-macos-windows) for the full
venv + Playwright setup. The short version:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
playwright install --with-deps chromium   # omit --with-deps on macOS/Windows
cp .env.example .env                       # then add OPENAI_API_KEY
```

Quick start:

```bash
# 1. Enter the nix dev shell
nix-shell

# 2. Install the package in editable mode
pip install -e '.[dev]'

# 3. Run the pipeline (requires OPENAI_API_KEY)
python -m phone_agent --site <retailer-url> --max-urls 5

# 4. Or research a list of retailers from an input file
cp retailers.example.txt retailers.txt
python -m phone_agent --sites-file retailers.txt --max-urls 5

# 5. Or run in dry-run mode (no LLM/Playwright network calls)
python -m phone_agent --site <fixture-server-url> --max-urls 5 --dry-run
```

Exit codes: `0` success, `2` configuration error, `3` zero valid records,
`4` pipeline failure.