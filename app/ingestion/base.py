from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.contracts.models import LightCurve


class IngestionError(RuntimeError):
    """Raised when a mission data product cannot be ingested safely."""


class LightCurveIngestor(Protocol):
    """Common adapter interface for mission-specific light-curve ingestion."""

    def ingest_file(self, source: str | Path) -> LightCurve:
        """Read one light-curve data product into the shared contract."""
        ...
