import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from pydantic import ValidationError

from phone_agent.config import Settings
from phone_agent.crew import crew
from phone_agent.discovery import discover_urls
from phone_agent.export import export_phones
from phone_agent.schemas import PhoneSpec, ValidatedPhones
from phone_agent.sources import load_sites_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("phone-agent")


def _parse_args(argv: list | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="phone-agent",
        description=(
            "CrewAI Phone Research Agent: discover, fetch, extract, "
            "validate, and export phone specs from one or more retailer URLs."
        ),
    )
    parser.add_argument(
        "--site",
        help="Retailer base URL to start discovery from",
    )
    parser.add_argument(
        "--sites-file",
        help=(
            "Path to a text file containing retailer links, one per line. "
            "Blank lines and lines starting with '#' are ignored."
        ),
    )
    parser.add_argument(
        "--max-urls",
        type=int,
        default=25,
        help="Maximum number of product pages to fetch per site (default: 25)",
    )
    parser.add_argument(
        "--out-dir",
        default="out",
        help="Output directory (default: out)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass the disk cache and re-fetch all pages",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the crew without LLM calls; exit 0 if pipeline setup OK",
    )
    args = parser.parse_args(argv)
    if not args.site and not args.sites_file:
        parser.error("one of --site or --sites-file is required")
    return args


def _load_sites(args: argparse.Namespace) -> List[str]:
    sites: List[str] = []
    if args.site:
        sites.append(args.site.strip())
    if args.sites_file:
        sites.extend(load_sites_file(Path(args.sites_file)))

    unique: List[str] = []
    seen = set()
    for site in sites:
        if site not in seen:
            seen.add(site)
            unique.append(site)
    return unique


def _extract_validated(result: object) -> Optional[ValidatedPhones]:
    candidates = [getattr(result, "pydantic", None)]
    for task_output in reversed(getattr(result, "tasks_output", []) or []):
        candidates.append(getattr(task_output, "pydantic", None))

    for candidate in candidates:
        if isinstance(candidate, ValidatedPhones):
            return candidate
    return None


def _write_rejected(rejected: list, out_dir: Path) -> None:
    if not rejected:
        return

    serializable = []
    for item in rejected:
        if isinstance(item, dict):
            record, reason = item.get("record"), item.get("reason")
        else:
            record, reason = item
        serializable.append(
            {
                "record": (
                    record.model_dump()
                    if hasattr(record, "model_dump")
                    else record
                ),
                "reason": reason,
            }
        )

    rejected_path = out_dir / "rejected.json"
    with open(rejected_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)


def _run_pipeline(args: argparse.Namespace) -> int:
    """Run the full crew pipeline and return exit code."""

    # Settings — will raise RuntimeError if NixOS env is wrong
    try:
        s = Settings()
    except (RuntimeError, ValidationError) as e:
        log.error(str(e))
        return 2

    if not s.openai_api_key:
        log.error("OPENAI_API_KEY must be set (see .env.example)")
        return 2

    try:
        sites = _load_sites(args)
    except (OSError, ValueError) as e:
        log.error(str(e))
        return 2

    if not sites:
        log.error("No retailer links provided")
        return 2

    # Override settings from CLI
    s.max_urls = args.max_urls
    s.out_dir = Path(args.out_dir)
    s.cache_dir = (
        Path(".cache/pages") if not args.no_cache else Path(".cache/pages.nocache")
    )
    s.headless = os.environ.get("PHONE_AGENT_HEADLESS", "true").lower() != "false"
    s.fetch_timeout_ms = int(
        os.environ.get("PHONE_AGENT_FETCH_TIMEOUT_MS", "60000")
    )
    s.max_fetch_retries = 2

    # Ensure dirs exist
    s.cache_dir.mkdir(parents=True, exist_ok=True)
    s.out_dir.mkdir(parents=True, exist_ok=True)

    # Dry-run: just verify the crew can start without network calls
    if args.dry_run:
        log.info(
            "Dry-run: pipeline setup OK for %d site(s) "
            "(no LLM/Playwright network calls)",
            len(sites),
        )
        return 0

    # --- Run the crew for each retailer link ---
    valid_records: List[PhoneSpec] = []
    rejected: list = []
    failed_sites = 0
    total_discovered = 0

    for site in sites:
        log.info("Processing site: %s", site)

        try:
            urls = discover_urls(site, s.max_urls, s)
        except Exception as exc:  # noqa: BLE001 - fall back to supplied URL
            log.warning(
                "Discovery failed for %s: %s; using the supplied URL", site, exc
            )
            urls = [site]
        total_discovered += len(urls)

        try:
            result = crew.kickoff(
                inputs={
                    "site": site,
                    "max_urls": s.max_urls,
                    "urls": urls,
                }
            )
        except Exception as exc:
            log.error("Pipeline exception for %s: %s", site, exc)
            failed_sites += 1
            continue

        validated = _extract_validated(result)
        if validated is None:
            log.error(
                "Pipeline result did not contain validated phone records for %s",
                site,
            )
            failed_sites += 1
            continue

        valid_records.extend(validated.records)
        rejected.extend(validated.rejected)

    if failed_sites == len(sites):
        log.error("All sites failed")
        return 4

    if not valid_records:
        log.error("Zero valid phone records — nothing to export")
        return 3

    # Export aggregated records
    try:
        export_phones(valid_records, s.out_dir)
    except ValueError as e:
        log.error(str(e))
        return 3

    _write_rejected(rejected, s.out_dir)

    # Logging / counts line
    found = len(valid_records) + len(rejected)
    fetched = total_discovered
    extracted = len(valid_records)

    counts_line = (
        f"found={found}, fetched={fetched}, "
        f"extracted={extracted}, valid={len(valid_records)}, "
        f"rejected={len(rejected)}"
    )
    log.info(counts_line)

    # Also append to run.log in out_dir
    run_log = s.out_dir / "run.log"
    with open(run_log, "a", encoding="utf-8") as f:
        f.write(counts_line + "\n")

    return 0


def main(argv: list | None = None) -> int:
    """CLI entrypoint. Returns exit code."""
    args = _parse_args(argv)

    # NixOS shell check — fail fast if PLAYWRIGHT env is set but path missing
    if os.environ.get("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD") == "1":
        browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
        if not browsers_path or not Path(browsers_path).exists():
            print(
                "You are on NixOS but not inside nix-shell. Run nix-shell and re-enter.",
                file=sys.stderr,
            )
            return 2

    return _run_pipeline(args)


if __name__ == "__main__":
    sys.exit(main())
