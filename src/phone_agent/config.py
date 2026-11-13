import os
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = Field(
        "", validation_alias=AliasChoices("OPENAI_API_KEY")
    )
    serper_api_key: str = Field(
        "", validation_alias=AliasChoices("SERPER_API_KEY")
    )
    model: str = Field(
        "gpt-4o-mini",
        validation_alias=AliasChoices("PHONE_AGENT_MODEL", "MODEL"),
    )
    max_urls: int = Field(
        25, validation_alias=AliasChoices("PHONE_AGENT_MAX_URLS", "MAX_URLS")
    )
    cache_dir: Path = Field(
        Path(".cache/pages"),
        validation_alias=AliasChoices("PHONE_AGENT_CACHE_DIR", "CACHE_DIR"),
    )
    out_dir: Path = Field(
        Path("out"),
        validation_alias=AliasChoices("PHONE_AGENT_OUT_DIR", "OUT_DIR"),
    )
    headless: bool = Field(
        True, validation_alias=AliasChoices("PHONE_AGENT_HEADLESS", "HEADLESS")
    )
    fetch_timeout_ms: int = Field(
        60_000,
        validation_alias=AliasChoices(
            "PHONE_AGENT_FETCH_TIMEOUT_MS", "FETCH_TIMEOUT_MS"
        ),
    )
    max_fetch_retries: int = Field(
        2,
        validation_alias=AliasChoices(
            "PHONE_AGENT_MAX_FETCH_RETRIES", "MAX_FETCH_RETRIES"
        ),
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def model_post_init(self, __context: object) -> None:
        if os.environ.get("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD") == "1":
            browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
            if not browsers_path or not Path(browsers_path).exists():
                raise RuntimeError(
                    "You are on NixOS but not inside nix-shell. Run nix-shell and re-enter."
                )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
