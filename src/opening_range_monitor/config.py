from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class AlertsConfig(BaseModel):
    channels: list[str] = Field(default_factory=lambda: ["log"])

    @field_validator("channels")
    @classmethod
    def normalize_channels(cls, value: list[str]) -> list[str]:
        channels = [channel.strip().lower() for channel in value if channel.strip()]
        return channels or ["log"]


class AppConfig(BaseModel):
    tickers: list[str] = Field(default_factory=lambda: ["AAPL", "TSLA", "NVDA"])
    analysis_window_minutes: int = Field(default=30, ge=1, le=120)
    opening_range_minutes: int = Field(default=5, ge=1, le=60)
    poll_interval_seconds: int = Field(default=60, ge=5, le=600)
    breakout_threshold_pct: float = Field(default=0.5, ge=0)
    volume_multiplier: float = Field(default=1.5, ge=0)
    momentum_lookback_minutes: int = Field(default=3, ge=1, le=60)
    momentum_threshold_pct: float = Field(default=0.3, ge=0)
    reversal_threshold_pct: float = Field(default=0.3, ge=0)
    stop_loss_pct: float = Field(default=0.4, gt=0)
    take_profit_pct: float = Field(default=0.8, gt=0)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)

    @field_validator("tickers")
    @classmethod
    def normalize_tickers(cls, value: list[str]) -> list[str]:
        tickers = []
        seen = set()
        for ticker in value:
            normalized = ticker.strip().upper()
            if not normalized or normalized in seen:
                continue
            tickers.append(normalized)
            seen.add(normalized)
        if not tickers:
            raise ValueError("At least one ticker is required.")
        return tickers

    @model_validator(mode="after")
    def validate_windows(self) -> "AppConfig":
        if self.opening_range_minutes >= self.analysis_window_minutes:
            raise ValueError("opening_range_minutes must be less than analysis_window_minutes.")
        if self.momentum_lookback_minutes >= self.analysis_window_minutes:
            raise ValueError("momentum_lookback_minutes must be less than analysis_window_minutes.")
        return self


def load_config(path: str | Path = "configs/default.yaml") -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        return AppConfig()
    with config_path.open("r", encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle) or {}
    return AppConfig.model_validate(raw)
