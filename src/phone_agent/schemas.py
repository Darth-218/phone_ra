from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field, validator


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"
    INR = "INR"

    @validator("__value__", pre=True)
    def _uppercase_currency(cls, v: object) -> object:
        if isinstance(v, str):
            return v.upper()
        return v


class RejectCode(str, Enum):
    EMPTY_NAME = "EMPTY_NAME"
    NO_SOURCE = "NO_SOURCE"
    BAD_PRICE = "BAD_PRICE"
    BAD_RAM = "BAD_RAM"
    BAD_STORAGE = "BAD_STORAGE"
    BAD_SCREEN = "BAD_SCREEN"
    BAD_BATTERY = "BAD_BATTERY"
    BAD_CAMERA = "BAD_CAMERA"
    DUP_URL_NAME = "DUP_URL_NAME"


class PhoneSpec(BaseModel):
    """Pydantic model for structured phone specifications.

    All task outputs reference this model via output_pydantic.
    Never use bare list[PhoneSpec] here; always wrap in PhoneList.
    """

    name: str = Field(..., description="Phone product name")
    brand: str = Field(default="", description="Phone brand/manufacturer")
    price: float = Field(..., description="Phone price")
    currency: str = Field(default="USD", description="Currency code")
    chipset: str = Field(default="", description="Processor/chipset model")
    ram_gb: int = Field(..., description="RAM in GB")
    storage_gb: int = Field(..., description="Storage in GB")
    screen_size_inch: float = Field(default=0.0, description="Screen size in inches")
    battery_mah: int = Field(default=0, description="Battery capacity in mAh")
    camera_mp: float = Field(default=0.0, description="Main rear camera in megapixels")
    os: str = Field(default="", description="Operating system")
    source_url: str = Field(..., description="Source URL of the product page")

    @validator("name")
    def _name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name must not be empty")
        return v.strip()

    @validator("price")
    def _price_positive(cls, v: float) -> float:
        if v is not None and v <= 0:
            raise ValueError("price must be positive")
        return v

    @validator("currency")
    def _uppercase_currency(cls, v: str) -> str:
        if not v:
            return "USD"
        return v.upper()

    @validator("source_url")
    def _source_url_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("source_url must not be empty")
        return v.strip()

    def __repr__(self) -> str:
        return (
            f"PhoneSpec(name={self.name!r}, price={self.price}, "
            f"currency={self.currency})"
        )


class UrlList(BaseModel):
    """Wrapper model for ordered list of unique retailer product URLs.

    Used as output_pydantic for Task 1 (URL discovery).
    Never use bare list[str] here.
    """

    urls: List[str] = Field(
        ..., description="Ordered list of unique retailer product URLs"
    )

    @validator("urls", each_item=True)
    def _urls_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("URL must not be empty")
        return v.strip()


class RawPageList(BaseModel):
    """Wrapper model for URL -> markdown content mapping.

    Used as output_pydantic for Task 2 (Playwright fetch).
    """

    pages: Dict[str, str] = Field(
        ..., description="URL -> markdown content mapping"
    )


class PhoneList(BaseModel):
    """Wrapper model for list of extracted phone specifications.

    Used as output_pydantic for Task 3 (extraction).
    """

    phones: List[PhoneSpec] = Field(
        ..., description="List of extracted phone specifications"
    )


class ValidatedPhones(BaseModel):
    """Wrapper model for validated phone records and rejection reasons.

    Each rejection is recorded as {"record": ..., "reason": "<code>"}
    in ValidatedPhones.rejected.
    The Validator agent calls validate_records(); it does not invent rules.
    """

    records: List[PhoneSpec] = Field(
        ..., description="Validated phone records"
    )
    rejected: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Each entry: {\"record\": PhoneSpec, \"reason\": RejectCode}",
    )

    def reject_record(self, record: PhoneSpec, code: RejectCode) -> None:
        self.rejected.append({"record": record, "reason": code})

    @staticmethod
    def validate_records(records: List[PhoneSpec]) -> ValidatedPhones:
        """Validate a list of PhoneSpec records against the rule set.

        Returns a ValidatedPhones instance with `.records` (the subset
        that passed) and `.rejected` (list of {"record": ..., "reason": "<code>"}).
        """
        rejected: List[Dict[str, Any]] = []
        valid: List[PhoneSpec] = []

        seen_url_names: set = set()

        for record in records:
            url_name = record.source_url.split("/")[-1] or "unknown"

            # EMPTY_NAME
            if not record.name or not record.name.strip():
                rejected.append({"record": record, "reason": RejectCode.EMPTY_NAME.value})
                continue

            # NO_SOURCE
            if not record.source_url:
                rejected.append({"record": record, "reason": RejectCode.NO_SOURCE.value})
                continue

            # DUP_URL_NAME - check for duplicate URL-based names
            if url_name in seen_url_names:
                rejected.append({"record": record, "reason": RejectCode.DUP_URL_NAME.value})
                continue
            seen_url_names.add(url_name)

            # BAD_PRICE
            if record.price is None or record.price <= 0:
                rejected.append({"record": record, "reason": RejectCode.BAD_PRICE.value})
                continue

            # BAD_RAM
            if record.ram_gb is None or record.ram_gb <= 0:
                rejected.append({"record": record, "reason": RejectCode.BAD_RAM.value})
                continue

            # BAD_STORAGE
            if record.storage_gb is None or record.storage_gb <= 0:
                rejected.append({"record": record, "reason": RejectCode.BAD_STORAGE.value})
                continue

            # BAD_SCREEN
            if record.screen_size_inch is None or record.screen_size_inch <= 0:
                rejected.append({"record": record, "reason": RejectCode.BAD_SCREEN.value})
                continue

            # BAD_BATTERY
            if record.battery_mah is None or record.battery_mah <= 0:
                rejected.append({"record": record, "reason": RejectCode.BAD_BATTERY.value})
                continue

            # BAD_CAMERA
            if record.camera_mp is None or record.camera_mp <= 0:
                rejected.append({"record": record, "reason": RejectCode.BAD_CAMERA.value})
                continue

            # All checks passed
            valid.append(record)

        return ValidatedPhones(records=valid, rejected=rejected)


def asdict(record: PhoneSpec) -> Dict[str, Any]:
    """Convert PhoneSpec to plain dict for serialization/JSON."""
    return {
        "name": record.name,
        "brand": record.brand,
        "price": record.price,
        "currency": record.currency,
        "chipset": record.chipset,
        "ram_gb": record.ram_gb,
        "storage_gb": record.storage_gb,
        "screen_size_inch": record.screen_size_inch,
        "battery_mah": record.battery_mah,
        "camera_mp": record.camera_mp,
        "os": record.os,
        "source_url": record.source_url,
    }


class ExportResult(BaseModel):
    """Result of export_phones() containing file paths."""

    csv_path: str
    xlsx_path: str

    def __repr__(self) -> str:
        return f"ExportResult(csv={self.csv_path}, xlsx={self.xlsx_path})"
