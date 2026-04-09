"""Stage base protocol with artifact guard pattern."""

from dataclasses import dataclass
from pathlib import Path

from loguru import logger


@dataclass
class StageResult:
    """Result of a pipeline stage execution."""

    stage_name: str
    artifact_path: Path
    skipped: bool
    error: str | None = None


def artifact_guard(output_path: Path) -> bool:
    """Return True if artifact already exists (cache hit), False otherwise.

    When True is returned, the caller should skip the stage and use the
    existing artifact from disk.
    """
    if output_path.exists():
        logger.info(
            "Cache hit: artifact exists at {path} — skipping stage",
            path=output_path,
        )
        return True
    return False
