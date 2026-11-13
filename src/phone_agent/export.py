import csv
from pathlib import Path
from typing import List

import pandas as pd

from phone_agent.schemas import PhoneSpec, ExportResult


def _format_price(price: float, currency: str) -> str:
    """Format price as a string for CSV/Excel output."""
    return f"{currency} {price:,.2f}"


def export_phones(records: List[PhoneSpec], out_dir: Path) -> ExportResult:
    """Export phone records to CSV and Excel.

    Fixed column order: name, brand, price, currency, chipset, ram_gb,
    storage_gb, screen_size_inch, battery_mah, camera_mp, os, source_url.

    UTF-8 CSV. Formatted Excel sheet 'Phones' with frozen header
    and autofilter.

    Raises ValueError on empty records.
    """
    if not records:
        raise ValueError("No valid phone records to export")

    out_dir.mkdir(parents=True, exist_ok=True)

    # Fixed column order
    columns = [
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

    # --- CSV ---
    csv_path = out_dir / "phones.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for rec in records:
            writer.writerow([
                rec.name,
                rec.brand,
                _format_price(rec.price, rec.currency),
                rec.currency,
                rec.chipset,
                rec.ram_gb,
                rec.storage_gb,
                rec.screen_size_inch,
                rec.battery_mah,
                rec.camera_mp,
                rec.os,
                rec.source_url,
            ])

    # --- Excel ---
    xlsx_path = out_dir / "phones.xlsx"
    df = pd.DataFrame([{
        "name": rec.name,
        "brand": rec.brand,
        "price": _format_price(rec.price, rec.currency),
        "currency": rec.currency,
        "chipset": rec.chipset,
        "ram_gb": rec.ram_gb,
        "storage_gb": rec.storage_gb,
        "screen_size_inch": rec.screen_size_inch,
        "battery_mah": rec.battery_mah,
        "camera_mp": rec.camera_mp,
        "os": rec.os,
        "source_url": rec.source_url,
    } for rec in records])

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Phones", index=False)
        ws = writer.sheets["Phones"]
        # Freeze top row
        ws.freeze_panes = "A2"
        # Autofilter
        ws.auto_filter.ref = f"A{1}:L{len(df) + 1}"

    return ExportResult(csv_path=str(csv_path), xlsx_path=str(xlsx_path))
