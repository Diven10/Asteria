from __future__ import annotations

from pathlib import Path

from app.contracts.models import LightCurve
from app.ingestion.tess import TessIngestor
from app.ingestion.kepler import KeplerIngestor
from app.ingestion.plato import PlatoSyntheticIngestor


class IngestionService:
    """Application-level entry point for TESS/Kepler/PLATO ingestion."""

    def __init__(
        self, 
        tess: TessIngestor | None = None,
        kepler: KeplerIngestor | None = None,
        plato: PlatoSyntheticIngestor | None = None,
    ) -> None:
        self.tess = tess or TessIngestor()
        self.kepler = kepler or KeplerIngestor()
        self.plato = plato or PlatoSyntheticIngestor()

    def ingest_tess_file(self, source: str | Path) -> LightCurve:
        return self.tess.ingest_file(source)

    def download_tess(
        self,
        target: str | int,
        *,
        sector: int | None = None,
        exptime: str | float | int | None = None,
        download_dir: str | Path | None = None,
    ) -> LightCurve:
        return self.tess.search_and_download(
            target,
            sector=sector,
            exptime=exptime,
            download_dir=download_dir,
        )

    def ingest_kepler_file(self, source: str | Path) -> LightCurve:
        return self.kepler.ingest_file(source)

    def download_kepler(
        self,
        target: str | int,
        *,
        quarter: int | None = None,
        campaign: int | None = None,
        exptime: str | float | int | None = None,
        download_dir: str | Path | None = None,
    ) -> LightCurve:
        return self.kepler.search_and_download(
            target,
            quarter=quarter,
            campaign=campaign,
            exptime=exptime,
            download_dir=download_dir,
        )

    def ingest_plato_synthetic_file(self, source: str | Path) -> LightCurve:
        return self.plato.ingest_file(source)
