import argparse
import json
import logging
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from phone_agent.config import Settings
from phone_agent.crew import crew
from phone_agent.export import export_phones
from phone_agent.schemas import ValidatedPhones

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
            "validate, and export phone specs from a retailer URL."
        ),
    )
    parser.add_argument(
        "--site",
        required=True,
        help="Retailer base URL to start discovery from",
    )
    parser.add_argument(
        "--max-urls",
        type=int,
        default=25,
        help="Maximum number of product pages to fetch (default: 25)",
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
    return parser.parse_args(argv)


def _run_pipeline(args: argparse.Namespace) -> int:
    """Run the full crew pipeline and return exit code."""

    # Settings — will raise RuntimeError if NixOS env is wrong
    try:
        s = Settings()
    except (RuntimeError, ValidationError) as e:
        log.error(str(e))
        return 2

    if not s.openai_api_key or not s.serper_api_key:
        log.error(
            "OPENAI_API_KEY and SERPER_API_KEY must be set (see .env.example)"
        )
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
        log.info("Dry-run: pipeline setup OK (no LLM/Playwright network calls)")
        return 0

    # --- Run the crew ---
    try:
        result = crew.kickoff(
            inputs={
                "site": args.site,
                "max_urls": s.max_urls,
            }
        )
    except Exception as exc:
        log.error(f"Pipeline exception: {exc}")
        return 4

    # --- Post-pipeline processing ---
    validated = getattr(result, "pydantic", None)
    if not isinstance(validated, ValidatedPhones):
        validated = getattr(result, "validated", None) or getattr(
            result, "phones", None
        )

    if not isinstance(validated, ValidatedPhones):
        log.error("Pipeline result did not contain validated phone records")
        return 4

    valid_records = validated.records
    rejected = validated.rejected

    if not valid_records:
        log.error("Zero valid phone records — nothing to export")
        return 3

    # Export
    try:
        export_phones(valid_records, s.out_dir)
    except ValueError as e:
        log.error(str(e))
        return 3

    # Write rejected.json if there are rejections
    if rejected:
        rejected_path = s.out_dir / "rejected.json"
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
        with open(rejected_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2)

    # Logging / counts line
    found = len(valid_records) + len(rejected)
    fetched = getattr(crew, "_tasks_running", 0) or s.max_urls
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
