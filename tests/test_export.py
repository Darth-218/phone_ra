import csv
from pathlib import Path

import pandas as pd

from phone_agent.export import export_phones
from phone_agent.schemas import PhoneSpec

EXPECTED_HEADER = [
    "name",
    "brand",
    "price",
    "currency",
    "chipset",
    "ram_gb",
    "storage_gb",
    "screen_size_inch",
    "battery_mah",
    "camera_mp",
    "os",
    "source_url",
]


def _records() -> list[PhoneSpec]:
    return [
        PhoneSpec(
            name="iPhone 15 Pro",
            brand="Apple",
            price=999.99,
            currency="USD",
            chipset="Apple A17 Pro",
            ram_gb=8,
            storage_gb=256,
            screen_size_inch=6.1,
            battery_mah=3274,
            camera_mp=48.0,
            os="iOS 17",
            source_url="http://example.com/l1",
        ),
        PhoneSpec(
            name="Galaxy S24",
            brand="Samsung",
            price=799.0,
            currency="USD",
            chipset="Snapdragon 8 Gen 3",
            ram_gb=8,
            storage_gb=128,
            screen_size_inch=6.2,
            battery_mah=4000,
            camera_mp=50.0,
            os="Android 14",
            source_url="http://example.com/l2",
        ),
    ]


def test_export_csv_structure(tmp_path: Path) -> None:
    """CSV has fixed column order and UTF-8 encoding."""
    out_dir = tmp_path / "out"
    export_phones(_records(), out_dir)

    csv_path = out_dir / "phones.csv"
    assert csv_path.exists()

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == EXPECTED_HEADER

    with open(csv_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert "iPhone 15 Pro" in lines[1]
    assert "Galaxy S24" in lines[2]


def test_export_excel_structure(tmp_path: Path) -> None:
    """Excel has 'Phones' sheet with frozen header and autofilter."""
    out_dir = tmp_path / "out"
    export_phones(_records()[:1], out_dir)

    xlsx_path = out_dir / "phones.xlsx"
    assert xlsx_path.exists()

    df = pd.read_excel(xlsx_path, sheet_name="Phones")
    assert len(df) == 1
    assert df.iloc[0]["name"] == "iPhone 15 Pro"

    from openpyxl import load_workbook

    wb = load_workbook(xlsx_path)
    ws = wb["Phones"]
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref is not None


def test_export_value_error_on_empty_records(tmp_path: Path) -> None:
    """export_phones raises ValueError on empty records."""
    out_dir = tmp_path / "out"
    try:
        export_phones([], out_dir)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "no valid phone records" in str(e).lower()
