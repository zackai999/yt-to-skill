"""Pydantic models for trading logic extraction schema."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, model_validator


class EntryCondition(BaseModel):
    """A single entry or exit condition in a trading strategy."""

    indicator: str
    condition: str
    value: str | None = None
    timeframe: str | None = None
    confirmation: str | None = None
    raw_text: str


class StrategyObject(BaseModel):
    """A trading strategy extracted from video content."""

    strategy_name: str
    market_conditions: list[str]
    entry_criteria: list[EntryCondition]
    exit_criteria: list[EntryCondition]
    indicators: list[str]
    risk_rules: list[str]
    unspecified_params: list[str]

    @model_validator(mode="after")
    def populate_unspecified_params(self) -> "StrategyObject":
        """Scan entry/exit criteria for None fields and populate unspecified_params paths."""
        paths: list[str] = []

        nullable_fields = ("value", "timeframe", "confirmation")

        for i, condition in enumerate(self.entry_criteria):
            for field_name in nullable_fields:
                if getattr(condition, field_name) is None:
                    paths.append(f"entry_criteria[{i}].{field_name}")

        for i, condition in enumerate(self.exit_criteria):
            for field_name in nullable_fields:
                if getattr(condition, field_name) is None:
                    paths.append(f"exit_criteria[{i}].{field_name}")

        self.unspecified_params = paths
        return self


class TradingLogicExtraction(BaseModel):
    """Complete extraction of trading logic from a video."""

    video_id: str
    source_language: str
    strategies: list[StrategyObject]
    is_strategy_content: bool = True

    def to_file(self, path: Path) -> None:
        """Write extraction to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2))

    @classmethod
    def from_file(cls, path: Path) -> "TradingLogicExtraction":
        """Load extraction from a JSON file."""
        data = json.loads(path.read_text())
        return cls(**data)
