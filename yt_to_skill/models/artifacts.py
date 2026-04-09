"""Pipeline artifact dataclasses with JSON serialization."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class VideoMetadata:
    """Metadata for a YouTube video."""

    video_id: str
    title: str
    description: str
    duration_seconds: float
    channel: str
    upload_date: str | None = None
    tags: list[str] = field(default_factory=list)

    def to_json(self, path: Path) -> None:
        """Serialize to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2))

    @classmethod
    def from_json(cls, path: Path) -> "VideoMetadata":
        """Deserialize from JSON file."""
        data = json.loads(path.read_text())
        return cls(**data)


@dataclass
class TranscriptArtifact:
    """Transcript extracted from a YouTube video."""

    video_id: str
    source_language: str
    segments: list[dict]
    method: Literal["captions", "whisper"]
    caption_quality: Literal["good", "poor", "missing"]

    def __post_init__(self) -> None:
        valid_methods = ("captions", "whisper")
        if self.method not in valid_methods:
            raise ValueError(
                f"method must be one of {valid_methods}, got '{self.method}'"
            )
        valid_qualities = ("good", "poor", "missing")
        if self.caption_quality not in valid_qualities:
            raise ValueError(
                f"caption_quality must be one of {valid_qualities}, got '{self.caption_quality}'"
            )

    def to_json(self, path: Path) -> None:
        """Serialize to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2))

    @classmethod
    def from_json(cls, path: Path) -> "TranscriptArtifact":
        """Deserialize from JSON file."""
        data = json.loads(path.read_text())
        return cls(**data)


@dataclass
class FilterResult:
    """Result of the non-strategy filter stage."""

    video_id: str
    is_strategy: bool
    confidence: float
    reason: str
    metadata_pass: bool
    transcript_pass: bool | None = None

    def to_json(self, path: Path) -> None:
        """Serialize to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2))

    @classmethod
    def from_json(cls, path: Path) -> "FilterResult":
        """Deserialize from JSON file."""
        data = json.loads(path.read_text())
        return cls(**data)
