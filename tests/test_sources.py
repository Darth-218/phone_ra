from pathlib import Path

import pytest

from phone_agent.sources import load_sites_file


def test_load_sites_file_basic(tmp_path: Path) -> None:
    path = tmp_path / "retailers.txt"
    path.write_text(
        "# comment line\n"
        "https://example.com/phones\n"
        "\n"
        "  https://example.org/mobiles  # inline comment\n",
        encoding="utf-8",
    )

    assert load_sites_file(path) == [
        "https://example.com/phones",
        "https://example.org/mobiles",
    ]


def test_load_sites_file_dedupes_preserving_order(tmp_path: Path) -> None:
    path = tmp_path / "retailers.txt"
    path.write_text(
        "https://example.com/a\n"
        "https://example.com/b\n"
        "https://example.com/a\n",
        encoding="utf-8",
    )

    assert load_sites_file(path) == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_load_sites_file_rejects_invalid_link(tmp_path: Path) -> None:
    path = tmp_path / "retailers.txt"
    path.write_text("example.com/phones\n", encoding="utf-8")

    with pytest.raises(ValueError, match="expected an http"):
        load_sites_file(path)


def test_load_sites_file_rejects_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "retailers.txt"
    path.write_text("# only comments\n\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no retailer links"):
        load_sites_file(path)


def test_load_sites_file_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        load_sites_file(tmp_path / "missing.txt")
