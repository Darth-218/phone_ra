from phone_agent.schemas import PhoneSpec, RejectCode, ValidatedPhones


def _spec(**overrides) -> PhoneSpec:
    data = dict(
        name="Valid Phone",
        price=100.0,
        currency="USD",
        chipset="CPU",
        ram_gb=8,
        storage_gb=256,
        screen_size_inch=6.1,
        battery_mah=4000,
        camera_mp=50.0,
        os="Android",
        source_url="http://example.com/l1",
    )
    data.update(overrides)
    return PhoneSpec(**data)


class TestValidateDeterministic:
    """Validation rules — deterministic Python, no LLM."""

    def test_bad_price_rejected(self):
        spec = PhoneSpec.model_construct(
            name="Valid Phone",
            price=0.0,
            currency="USD",
            chipset="CPU",
            ram_gb=8,
            storage_gb=256,
            screen_size_inch=6.1,
            battery_mah=4000,
            camera_mp=50.0,
            os="Android",
            source_url="http://example.com/l1",
        )
        vl = ValidatedPhones.validate_records([spec])
        assert len(vl.rejected) == 1
        assert vl.rejected[0]["reason"] == RejectCode.BAD_PRICE.value

    def test_bad_ram_rejected(self):
        vl = ValidatedPhones.validate_records([_spec(ram_gb=0)])
        assert len(vl.rejected) == 1
        assert vl.rejected[0]["reason"] == RejectCode.BAD_RAM.value

    def test_bad_storage_rejected(self):
        vl = ValidatedPhones.validate_records([_spec(storage_gb=0)])
        assert len(vl.rejected) == 1
        assert vl.rejected[0]["reason"] == RejectCode.BAD_STORAGE.value

    def test_bad_screen_rejected(self):
        vl = ValidatedPhones.validate_records([_spec(screen_size_inch=0)])
        assert len(vl.rejected) == 1
        assert vl.rejected[0]["reason"] == RejectCode.BAD_SCREEN.value

    def test_bad_battery_rejected(self):
        vl = ValidatedPhones.validate_records([_spec(battery_mah=0)])
        assert len(vl.rejected) == 1
        assert vl.rejected[0]["reason"] == RejectCode.BAD_BATTERY.value

    def test_bad_camera_rejected(self):
        vl = ValidatedPhones.validate_records([_spec(camera_mp=0)])
        assert len(vl.rejected) == 1
        assert vl.rejected[0]["reason"] == RejectCode.BAD_CAMERA.value

    def test_dup_url_name_rejected(self):
        spec1 = _spec(name="Phone A", source_url="http://example.com/a")
        spec2 = _spec(name="Phone B", source_url="http://example.com/a")
        vl = ValidatedPhones.validate_records([spec1, spec2])
        assert len(vl.rejected) == 1
        assert vl.rejected[0]["reason"] == RejectCode.DUP_URL_NAME.value

    def test_valid_record_passes(self):
        spec = _spec()
        vl = ValidatedPhones.validate_records([spec])
        assert len(vl.records) == 1
        assert len(vl.rejected) == 0
        assert vl.records[0] is spec

    def test_mixed_rejections(self):
        specs = [
            _spec(name="Phone A", source_url="http://example.com/a"),
            _spec(name="Phone B", ram_gb=0, source_url="http://example.com/b"),
            _spec(name="Phone C", source_url="http://example.com/c"),
        ]
        vl = ValidatedPhones.validate_records(specs)
        assert len(vl.records) == 2
        assert len(vl.rejected) == 1
        assert vl.rejected[0]["reason"] == RejectCode.BAD_RAM.value
