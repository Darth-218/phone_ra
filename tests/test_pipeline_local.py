import os
import subprocess
import sys
from pathlib import Path

from phone_agent.export import export_phones
from phone_agent.schemas import PhoneSpec

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = Path(sys.prefix) / "bin" / "python"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def _record() -> PhoneSpec:
    return PhoneSpec(
        name="iPhone 15 Pro",
        brand="Apple",
        price=999.0,
        currency="USD",
        chipset="Apple A17 Pro",
        ram_gb=8,
        storage_gb=256,
        screen_size_inch=6.1,
        battery_mah=3274,
        camera_mp=48.0,
        os="iOS 17",
        source_url="http://example.com/iphone",
    )


def test_pipeline_export_local(tmp_path: Path) -> None:
    """Export stage writes phones.csv + phones.xlsx from local records."""
    export_phones([_record()], tmp_path / "out")

    csv_path = tmp_path / "out" / "phones.csv"
    xlsx_path = tmp_path / "out" / "phones.xlsx"

    assert csv_path.exists()
    assert xlsx_path.exists()
    assert "iPhone 15 Pro" in csv_path.read_text(encoding="utf-8")


def test_cli_dry_run(tmp_path: Path) -> None:
    """CLI dry run exits 0 with no third-party network calls."""
    env = {
        **os.environ,
        "OPENAI_API_KEY": "sk-test",
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "0",
    }
    env.pop("PLAYWRIGHT_BROWSERS_PATH", None)

    result = subprocess.run(
        [
            PYTHON,
            "-m",
            "phone_agent",
            "--site",
            "http://localhost/fixture",
            "--max-urls",
            "5",
            "--out-dir",
            str(tmp_path / "out"),
            "--dry-run",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "Dry-run" in result.stderr


def test_cli_missing_api_keys_exits_2(tmp_path: Path) -> None:
    """CLI exits 2 when required API keys are absent."""
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    env.pop("OPENAI_API_KEY", None)
    env.pop("PLAYWRIGHT_BROWSERS_PATH", None)
    env["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "0"

    result = subprocess.run(
        [
            PYTHON,
            "-m",
            "phone_agent",
            "--site",
            "http://localhost/fixture",
            "--out-dir",
            str(tmp_path / "out"),
            "--dry-run",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 2


def test_cli_dry_run_with_sites_file(tmp_path: Path) -> None:
    """CLI accepts a file of retailer links and reports how many were loaded."""
    sites_file = tmp_path / "retailers.txt"
    sites_file.write_text(
        "# sample retailers\n"
        "https://example.com/phones\n"
        "https://example.org/mobiles\n",
        encoding="utf-8",
    )

    env = {
        **os.environ,
        "OPENAI_API_KEY": "sk-test",
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "0",
    }
    env.pop("PLAYWRIGHT_BROWSERS_PATH", None)

    result = subprocess.run(
        [
            PYTHON,
            "-m",
            "phone_agent",
            "--sites-file",
            str(sites_file),
            "--out-dir",
            str(tmp_path / "out"),
            "--dry-run",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "2 site(s)" in result.stderr


def test_cli_requires_site_or_sites_file(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    env["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "0"
    env.pop("PLAYWRIGHT_BROWSERS_PATH", None)

    result = subprocess.run(
        [PYTHON, "-m", "phone_agent", "--dry-run"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 2
    assert "--sites-file" in result.stderr
