from typing import Any, Dict, List

from phone_agent.schemas import PhoneSpec, RejectCode, ValidatedPhones


class Validator:
    """Deterministic validation gatekeeper.

    The Validator agent is instructed to call validate_records();
    it does not invent rules.
    """

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
                rejected.append({"record": dict(record), "reason": RejectCode.EMPTY_NAME.value})
                continue

            # NO_SOURCE
            if not record.source_url:
                rejected.append({"record": dict(record), "reason": RejectCode.NO_SOURCE.value})
                continue

            # DUP_URL_NAME - check for duplicate URL-based names
            if url_name in seen_url_names:
                rejected.append({"record": dict(record), "reason": RejectCode.DUP_URL_NAME.value})
                continue
            seen_url_names.add(url_name)

            # BAD_PRICE
            if record.price is None or record.price <= 0:
                rejected.append({"record": dict(record), "reason": RejectCode.BAD_PRICE.value})
                continue

            # BAD_RAM
            if record.ram_gb is None or record.ram_gb <= 0:
                rejected.append({"record": dict(record), "reason": RejectCode.BAD_RAM.value})
                continue

            # BAD_STORAGE
            if record.storage_gb is None or record.storage_gb <= 0:
                rejected.append({"record": dict(record), "reason": RejectCode.BAD_STORAGE.value})
                continue

            # BAD_SCREEN
            if record.screen_size_inch is None or record.screen_size_inch <= 0:
                rejected.append({"record": dict(record), "reason": RejectCode.BAD_SCREEN.value})
                continue

            # BAD_BATTERY
            if record.battery_mah is None or record.battery_mah <= 0:
                rejected.append({"record": dict(record), "reason": RejectCode.BAD_BATTERY.value})
                continue

            # BAD_CAMERA
            if record.camera_mp is None or record.camera_mp <= 0:
                rejected.append({"record": dict(record), "reason": RejectCode.BAD_CAMERA.value})
                continue

            # All checks passed
            valid.append(record)

        return ValidatedPhones(records=valid, rejected=rejected)
