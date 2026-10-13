from __future__ import annotations

import csv
import pytest
from pathlib import Path

from app.contracts.models import Cadence, Mission
from app.ingestion.base import IngestionError
from app.ingestion.plato import PlatoSyntheticIngestor, PlatoIngestionConfig

def test_ingest_plato_synthetic_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "plato_test.csv"
    with csv_file.open("w", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "flux", "flux_err"])
        writer.writerow(["0.0", "1.0", "0.01"])
        writer.writerow(["0.1", "1.01", "0.01"])
        writer.writerow(["0.2", "0.99", "0.01"])
        
    ingestor = PlatoSyntheticIngestor()
    lc = ingestor.ingest_file(csv_file)
    
    assert lc.mission == Mission.PLATO_SYNTHETIC
    assert lc.target_id == "plato_test"
    assert len(lc.time) == 3
    assert len(lc.flux) == 3
    assert lc.flux_error is not None
    assert len(lc.flux_error) == 3
    assert lc.time[0] == 0.0
    assert lc.flux[0] == 1.0

def test_ingest_plato_missing_required_columns(tmp_path: Path) -> None:
    csv_file = tmp_path / "plato_bad.csv"
    with csv_file.open("w", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["wrong_time", "wrong_flux"])
        writer.writerow(["0.0", "1.0"])
        
    ingestor = PlatoSyntheticIngestor()
    with pytest.raises(IngestionError, match="missing required time/flux columns"):
        ingestor.ingest_file(csv_file)
        
def test_ingest_plato_without_flux_err(tmp_path: Path) -> None:
    csv_file = tmp_path / "plato_no_err.csv"
    with csv_file.open("w", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "flux"])
        writer.writerow(["0.0", "1.0"])
        writer.writerow(["0.1", "1.01"])
        
    ingestor = PlatoSyntheticIngestor()
    lc = ingestor.ingest_file(csv_file)
    assert lc.flux_error is None
    assert len(lc.time) == 2
