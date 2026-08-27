"""Configuration: env vars via pydantic-settings, plus the user-editable YAML config."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScrapeTarget(BaseModel):
    name: str
    url: str
    item_selector: str
    title_selector: str
    link_selector: str
    link_attr: str = "href"
    base_url: str = ""


class LeagueConfig(BaseModel):
    name: str
    competition_code: str
    rss_feeds: list[str] = Field(default_factory=list)
    scrape_targets: list[ScrapeTarget] = Field(default_factory=list)


class YamlConfig(BaseModel):
    timezone: str = "UTC"
    digest_cron: str = "0 8 * * *"
    fixture_lookahead_days: int = 7
    news_max_age_hours: int = 48
    leagues: list[LeagueConfig] = Field(default_factory=list)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: Literal["anthropic", "ollama"] = "anthropic"

    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-haiku-4-5"

    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.1"

    football_data_api_token: Optional[str] = None

    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    config_path: str = "config.yaml"
    digest_cron: Optional[str] = None  # overrides yaml digest_cron when set


def load_yaml_config(path: str) -> YamlConfig:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Config file not found at '{path}'. Copy config.example.yaml to config.yaml first."
        )
    with p.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return YamlConfig.model_validate(raw)


def get_settings() -> Settings:
    return Settings()


def redact(settings: Settings) -> dict:
    """Return a settings view safe to expose over HTTP - secret values are masked."""

    def mask(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        return "***set***"

    return {
        "llm_provider": settings.llm_provider,
        "anthropic_api_key": mask(settings.anthropic_api_key),
        "anthropic_model": settings.anthropic_model,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "football_data_api_token": mask(settings.football_data_api_token),
        "telegram_bot_token": mask(settings.telegram_bot_token),
        "telegram_chat_id": mask(settings.telegram_chat_id),
        "config_path": settings.config_path,
        "digest_cron": settings.digest_cron,
    }
