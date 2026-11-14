# Usage Guide

Full reference for running the CrewAI Phone Research Agent.

---

## 1. What it does

Given one or more retailer links, the agent:

1. Discovers phone product pages on each retailer domain.
2. Fetches and renders pages with headless Playwright (with a disk cache).
3. Extracts structured phone specs from the page content.
4. Validates the records with deterministic rules.
5. Writes `phones.csv`, `phones.xlsx`, and `out/rejected.json`.

---

## 2. Installation

### 2.1 NixOS (primary supported path)

```bash
nix-shell                  # creates and activates .venv, sets Playwright paths
pip install -e '.[dev]'    # install project + dev dependencies
```

Do **not** run `playwright install` on NixOS. The shell provides Chromium via
`PLAYWRIGHT_BROWSERS_PATH`.

### 2.2 Non-Nix systems (Linux, macOS, Windows)

The project runs anywhere Python 3.11+ and Playwright are supported. You manage
the Python environment and Chromium yourself; the NixOS startup checks do not
apply.

#### Prerequisites

- Python 3.11 or newer (`python3 --version`)
- `pip` and `venv`
- `git`
- On Linux, the system libraries Chromium needs (see below)

#### Step 1: Create a virtual environment

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

#### Step 2: Install the project

```bash
pip install --upgrade pip
pip install -e '.[dev]'
```

This installs the pinned `playwright==1.49.0` package, so the browser you install
next will match the driver.

#### Step 3: Install Chromium for Playwright

```bash
# Linux and macOS
playwright install chromium

# Linux: also install missing OS libraries automatically
playwright install --with-deps chromium

# Windows
playwright install chromium
```

Browsers are installed under `~/.cache/ms-playwright` (Linux/macOS) or
`%USERPROFILE%\AppData\Local\ms-playwright` (Windows). Do **not** set
`PLAYWRIGHT_BROWSERS_PATH` unless you deliberately want a custom location.

#### Step 4: Install Linux system libraries (if needed)

`playwright install --with-deps chromium` handles this on Debian/Ubuntu and
Fedora. If you prefer manual installation:

```bash
# Debian / Ubuntu
sudo apt-get update
sudo apt-get install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
  libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
  libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2

# Fedora
sudo dnf install -y nss nspr atk at-spi2-atk cups-libs libdrm libxkbcommon \
  libXcomposite libXdamage libXfixes libXrandr mesa-libgbm alsa-lib \
  pango cairo
```

macOS and Windows do not need extra system packages.

#### Step 5: Configure API keys

```bash
cp .env.example .env
```

Edit `.env` and set:

```bash
OPENAI_API_KEY=sk-...
```

#### Step 6: Verify the setup

```bash
python -m phone_agent --help
python -m phone_agent --site https://www.apple.com/iphone/ --dry-run
```

The dry run exits `0` without calling the LLM or launching a browser.

#### Step 7: Run the pipeline

```bash
python -m phone_agent --site https://www.apple.com/iphone/ --max-urls 5
```

or with a file of retailers:

```bash
cp retailers.example.txt retailers.txt
python -m phone_agent --sites-file retailers.txt --max-urls 5
```

#### Step 8: Run the tests (optional)

```bash
pytest
```

The tests mock the LLM and use a local fixture HTTP server. They do not need
real API keys or live retailer sites, but Playwright tests may still launch
Chromium.

#### Non-Nix troubleshooting

- `playwright: command not found` — activate the virtual environment first.
- `Executable doesn't exist ...` — run `playwright install chromium`.
- Missing shared library errors on Linux — run
  `playwright install --with-deps chromium` or install the packages listed above.
- `libstdc++.so.6: cannot open shared object file` when importing NumPy/Pandas —
  install your distribution's GCC runtime (`libstdc++`) package, or ensure the
  correct 64-bit library is on `LD_LIBRARY_PATH`.
- If you use a custom browser location, set `PLAYWRIGHT_BROWSERS_PATH` to that
  directory; otherwise leave it unset.

---

## 3. Required configuration

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Then set the required key:

```bash
OPENAI_API_KEY=sk-...
```

`OPENAI_API_KEY` is required. The program exits with code `2` if it is missing.
No search API key is needed: URL discovery uses the retailer's sitemap and
same-site links.

---

## 4. Quick start

```bash
# Single retailer
python -m phone_agent --site https://www.apple.com/iphone/ --max-urls 5

# Multiple retailers from a file
cp retailers.example.txt retailers.txt
python -m phone_agent --sites-file retailers.txt --max-urls 5

# Verify setup without LLM or network calls
python -m phone_agent --site https://www.apple.com/iphone/ --dry-run
```

---

## 5. CLI options

```bash
python -m phone_agent (--site URL | --sites-file FILE) [options]
```

| Option | Default | Description |
| --- | --- | --- |
| `--site URL` | none | A single retailer base URL to start discovery from. |
| `--sites-file FILE` | none | Path to a text file of retailer links, one per line. |
| `--max-urls N` | `25` | Maximum product pages to fetch **per site**. |
| `--out-dir DIR` | `out` | Directory for `phones.csv`, `phones.xlsx`, `rejected.json`, and `run.log`. |
| `--no-cache` | off | Bypass the page cache and re-fetch every page. |
| `--dry-run` | off | Validate configuration and inputs, then exit without LLM or Playwright calls. |
| `-h`, `--help` | | Show all options and exit. |

At least one of `--site` or `--sites-file` is required. If both are supplied,
the single `--site` URL is processed first, then the links from the file.

### Examples

```bash
# Single site, limit to 10 pages
python -m phone_agent --site https://www.samsung.com/us/smartphones/ --max-urls 10

# Multiple sites, custom output directory
python -m phone_agent --sites-file retailers.txt --out-dir results

# Ignore cached pages
python -m phone_agent --site https://www.mi.com/global/phones/ --no-cache

# Setup check only
python -m phone_agent --sites-file retailers.txt --dry-run
```

### How URL discovery works

No search API key is used. For each retailer link, discovery runs before the
CrewAI crew:

1. Reads `robots.txt` for `Sitemap:` entries, falling back to `/sitemap.xml`.
2. Walks sitemap indexes and collects `<loc>` URLs (up to a safe limit).
3. Crawls the supplied page with Playwright and collects same-site `<a href>` links.
4. Keeps product-like URLs (`phone`, `mobile`, `smartphone`, `product`, model
   numbers) and drops cart, login, blog, support, accessory, and similar pages.
5. Normalizes URLs, removes tracking parameters and fragments, dedupes, and caps
   the result at `--max-urls`.
6. Falls back to the supplied URL if nothing else is found.

Discovery is best-effort: sites with no sitemap or JS-only listings still work,
but may yield fewer pages than a search-engine-based approach.

---

## 6. Retailer input file format

`--sites-file` expects a plain text file:

```text
# One retailer link per line.
# Blank lines and comments are ignored.
https://www.apple.com/iphone/
https://www.samsung.com/us/smartphones/   # inline comments are stripped
https://www.mi.com/global/phones/
```

Rules:

- Each non-empty line must start with `http://` or `https://`.
- Lines starting with `#` are ignored.
- Text after `#` on a line is treated as a comment.
- Leading/trailing whitespace is trimmed.
- Duplicate links are removed while preserving order.
- An empty file, or a file with only comments, is a configuration error (exit `2`).

`retailers.txt` is gitignored so your personal list is not committed. Start from
`retailers.example.txt`.

---

## 7. Environment variables

Settings are loaded from the process environment and from `.env`.

| Variable | Default | Description |
| --- | --- | --- |
| `OPENAI_API_KEY` | required | OpenAI API key used by the LLM. |
| `PHONE_AGENT_MODEL` | `gpt-4o-mini` | LLM model name. Also accepts `MODEL`. |
| `PHONE_AGENT_MAX_URLS` | `25` | Default page cap. Overridden by `--max-urls`. Also accepts `MAX_URLS`. |
| `PHONE_AGENT_CACHE_DIR` | `.cache/pages` | Page cache directory. Overridden by `--no-cache`. Also accepts `CACHE_DIR`. |
| `PHONE_AGENT_OUT_DIR` | `out` | Output directory. Overridden by `--out-dir`. Also accepts `OUT_DIR`. |
| `PHONE_AGENT_HEADLESS` | `true` | Set to `false` to run Chromium with a visible window. Also accepts `HEADLESS`. |
| `PHONE_AGENT_FETCH_TIMEOUT_MS` | `60000` | Per-page Playwright navigation timeout in milliseconds. Also accepts `FETCH_TIMEOUT_MS`. |
| `PHONE_AGENT_MAX_FETCH_RETRIES` | `2` | Fetch retry attempts with exponential backoff. Also accepts `MAX_FETCH_RETRIES`. |
| `PLAYWRIGHT_BROWSERS_PATH` | set by `nix-shell` | Location of the Nix-provided Chromium. |
| `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD` | set by `nix-shell` | Must be `1` inside the Nix shell. |

CLI flags take precedence over environment variables for `--max-urls`,
`--out-dir`, and `--no-cache`.

---

## 8. Outputs

All outputs are written to `--out-dir` (default `out/`).

### `phones.csv`

UTF-8 CSV with a fixed column order:

| Column | Description |
| --- | --- |
| `name` | Phone product name |
| `brand` | Manufacturer/brand |
| `price` | Formatted price, e.g. `USD 999.00` |
| `currency` | ISO currency code |
| `chipset` | Processor/chipset |
| `ram_gb` | RAM in GB |
| `storage_gb` | Storage in GB |
| `screen_size_inch` | Display size in inches |
| `battery_mah` | Battery capacity in mAh |
| `camera_mp` | Main rear camera in megapixels |
| `os` | Operating system |
| `source_url` | Product page URL |

### `phones.xlsx`

Excel workbook with a `Phones` sheet, frozen header row, and autofilter.

### `rejected.json`

Written only when at least one record fails validation:

```json
[
  {
    "record": { "name": "...", "price": 0, "...": "..." },
    "reason": "BAD_PRICE"
  }
]
```

### `run.log`

Append-only log containing the final counts line:

```text
found=12, fetched=10, extracted=12, valid=10, rejected=2
```

### Page cache

Cached pages are stored in `.cache/pages/` (or `PHONE_AGENT_CACHE_DIR`):

- `{sha256(url)[:16]}.md` — cleaned Markdown page content
- `{sha256(url)[:16]}.meta.json` — cache metadata

Use `--no-cache` to bypass reads and writes for a run.

---

## 9. Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success: records were exported. |
| `2` | Configuration error: missing API keys, bad input file, no retailer links, or not inside `nix-shell`. |
| `3` | Zero valid records after validation; no export written. |
| `4` | Pipeline failure: all sites failed or a pipeline exception occurred. |

If some sites fail but others produce valid records, the run continues and
exports the successful results.

---

## 10. Pipeline overview

URL discovery runs deterministically before the crew. The CrewAI crew then runs
four agents sequentially:

| Agent | Role | Tools |
| --- | --- | --- |
| Fetcher | Renders pages and returns Markdown | `PlaywrightFetchTool` |
| Extractor | Maps Markdown to `PhoneSpec` records | none |
| Validator | Applies deterministic rules | none |
| Reporter | Writes CSV/Excel and counts | none |

All agents use `temperature=0.1`, `allow_delegation=False`, `max_iter=8`, and
sequential execution with memory disabled for deterministic output.

---

## 11. Data model and validation

Each extracted record is a `PhoneSpec`:

`name`, `brand`, `price`, `currency`, `chipset`, `ram_gb`, `storage_gb`,
`screen_size_inch`, `battery_mah`, `camera_mp`, `os`, `source_url`.

Validation rejects records with these codes:

| Code | Rule |
| --- | --- |
| `EMPTY_NAME` | `name` is missing or blank |
| `NO_SOURCE` | `source_url` is missing |
| `BAD_PRICE` | `price <= 0` |
| `BAD_RAM` | `ram_gb <= 0` |
| `BAD_STORAGE` | `storage_gb <= 0` |
| `BAD_SCREEN` | `screen_size_inch <= 0` |
| `BAD_BATTERY` | `battery_mah <= 0` |
| `BAD_CAMERA` | `camera_mp <= 0` |
| `DUP_URL_NAME` | Duplicate URL-derived name |

Validated records are exported; rejected records go to `rejected.json`.

---

## 12. Development and testing

```bash
pytest                      # run the test suite
pytest tests/test_sources.py
python -m phone_agent --help
```

On some NixOS setups, NumPy-based dependencies may require the GCC runtime on
`LD_LIBRARY_PATH`:

```bash
export LD_LIBRARY_PATH=$(nix eval --raw nixpkgs#gcc.cc.lib)/lib64
pytest
```

---

## 13. Troubleshooting

### "You are on NixOS but not inside nix-shell"

Enter the shell first:

```bash
nix-shell
```

### Browser not found or Playwright version mismatch

The `playwright==...` pin in `pyproject.toml` must match the nixpkgs
`playwright-driver` version:

```bash
nix eval nixpkgs#playwright-driver.version
```

Update the pin in `pyproject.toml`. Never run `playwright install` on NixOS.

### Missing API key

Set `OPENAI_API_KEY` in `.env` or the environment. The program exits with code
`2` otherwise.

### Zero valid records

The pipeline ran but validation rejected every record. Check `out/rejected.json`
for the reasons, and confirm the retailer pages expose phone specs in their HTML.

### `--sites-file` is rejected

Ensure every non-comment line starts with `http://` or `https://`, and that the
file contains at least one link.

---

## 14. Known limitations

- Bot detection and CAPTCHAs can block fetching on some retailers.
- JavaScript-heavy pages may render incompletely in headless Chromium.
- Each run makes LLM calls, so cost scales with the number of pages and sites.
- Multi-site runs are sequential, not parallel.
- The Playwright pin must be kept aligned with the nixpkgs driver version.
