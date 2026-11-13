import pytest

from phone_agent.schemas import (
    Currency,
    PhoneList,
    PhoneSpec,
    RawPageList,
    RejectCode,
    UrlList,
    ValidatedPhones,
)


class TestPhoneSpec:
    def test_valid_phone_spec(self):
        spec = PhoneSpec(
            name="iPhone 15 Pro",
            brand="Apple",
            price=999.99,
            currency=Currency.USD,
            chipset="Apple A17 Pro",
            ram_gb=8,
            storage_gb=256,
            screen_size_inch=6.1,
            battery_mah=3274,
            camera_mp=48.0,
            os="iOS 17",
            source_url="http://example.com/phone",
        )
        assert spec.name == "iPhone 15 Pro"
        assert spec.brand == "Apple"
        assert spec.price == 999.99
        assert spec.currency == Currency.USD
        assert spec.chipset == "Apple A17 Pro"
        assert spec.ram_gb == 8
        assert spec.storage_gb == 256
        assert spec.screen_size_inch == 6.1
        assert spec.battery_mah == 3274
        assert spec.camera_mp == 48.0
        assert spec.os == "iOS 17"
        assert spec.source_url == "http://example.com/phone"

    def test_empty_name(self):
        with pytest.raises(ValueError, match="name must not be empty"):
            PhoneSpec(
                name="",
                price=999.99,
                currency=Currency.USD,
                ram_gb=8,
                storage_gb=256,
                source_url="http://example.com/phone",
            )

    def test_currency_uppercases(self):
        spec = PhoneSpec(
            name="Test Phone",
            price=100.0,
            currency="eur",
            ram_gb=8,
            storage_gb=128,
            source_url="http://example.com",
        )
        assert spec.currency == Currency.EUR

    def test_negative_price_rejected(self):
        with pytest.raises(ValueError, match="price must be positive"):
            PhoneSpec(
                name="Test Phone",
                price=-50.0,
                currency=Currency.USD,
                ram_gb=8,
                storage_gb=128,
                source_url="http://example.com",
            )


class TestUrlList:
    def test_valid_url_list(self):
        urls = UrlList(urls=["http://example.com/a", "http://example.com/b"])
        assert urls.urls == ["http://example.com/a", "http://example.com/b"]

    def test_empty_url_rejected(self):
        with pytest.raises(ValueError, match="URL must not be empty"):
            UrlList(urls=["http://example.com/a", ""])


class TestWrapperModels:
    def test_phone_list(self):
        spec = PhoneSpec(
            name="Pixel 8",
            price=699.0,
            ram_gb=8,
            storage_gb=128,
            source_url="http://example.com/pixel",
        )
        assert PhoneList(phones=[spec]).phones[0] is spec

    def test_raw_page_list(self):
        pages = RawPageList(pages={"http://example.com": "# markdown"})
        assert pages.pages["http://example.com"] == "# markdown"


class TestRejectCode:
    def test_all_codes(self):
        assert RejectCode.EMPTY_NAME.value == "EMPTY_NAME"
        assert RejectCode.NO_SOURCE.value == "NO_SOURCE"
        assert RejectCode.BAD_PRICE.value == "BAD_PRICE"
        assert RejectCode.BAD_RAM.value == "BAD_RAM"
        assert RejectCode.BAD_STORAGE.value == "BAD_STORAGE"
        assert RejectCode.BAD_SCREEN.value == "BAD_SCREEN"
        assert RejectCode.BAD_BATTERY.value == "BAD_BATTERY"
        assert RejectCode.BAD_CAMERA.value == "BAD_CAMERA"
        assert RejectCode.DUP_URL_NAME.value == "DUP_URL_NAME"


class TestCurrency:
    def test_values(self):
        assert Currency.USD.value == "USD"
        assert Currency.EUR.value == "EUR"
        assert Currency.INR.value == "INR"


class TestValidatedPhones:
    def test_validate_valid_record(self):
        spec = PhoneSpec(
            name="Galaxy S24",
            price=799.0,
            ram_gb=8,
            storage_gb=256,
            screen_size_inch=6.2,
            battery_mah=4000,
            camera_mp=50.0,
            source_url="http://example.com/s24",
        )
        result = ValidatedPhones.validate_records([spec])
        assert result.records == [spec]
        assert result.rejected == []
