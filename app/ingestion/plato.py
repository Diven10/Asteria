from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import csv

import numpy as np

from app.contracts.models import Cadence, LightCurve, Mission
from app.ingestion.base import IngestionError

@dataclass(frozen=True, slots=True)
class PlatoIngestionConfig:
    """Configuration for PLATO synthetic light-curve ingestion."""
    time_column: str = "time"
    flux_column: str = "flux"
    flux_err_column: str = "flux_err"

class PlatoSyntheticIngestor:
    """Adapter for PLATO synthetic light curves (CSV).
    Note: PLATO is not yet launched/providing live data. This is strictly
    for synthetic-validated readiness framing.
    """

    def __init__(self, config: PlatoIngestionConfig | None = None) -> None:
        self.config = config or PlatoIngestionConfig()

    def ingest_file(self, source: str | Path) -> LightCurve:
        source_string = str(source)
        if not source_string.strip():
            raise ValueError("PLATO source cannot be empty.")

        path = Path(source_string)
        if not path.is_file():
            raise FileNotFoundError(f"PLATO synthetic light-curve file not found: {path}")

        time_vals = []
        flux_vals = []
        flux_err_vals = []

        try:
            with path.open("r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if not reader.fieldnames:
                    raise IngestionError("PLATO synthetic file is empty or has no header.")
                    
                fieldnames = [c.lower().strip() for c in reader.fieldnames]
                if self.config.time_column.lower() not in fieldnames or self.config.flux_column.lower() not in fieldnames:
                    raise IngestionError("PLATO synthetic file missing required time/flux columns.")
                
                has_err = self.config.flux_err_column.lower() in fieldnames
                
                # We do this mapping properly:
                # find actual column names in the file matching our config (case-insensitive)
                t_col = next(c for c in reader.fieldnames if c.lower().strip() == self.config.time_column.lower())
                f_col = next(c for c in reader.fieldnames if c.lower().strip() == self.config.flux_column.lower())
                fe_col = next(c for c in reader.fieldnames if c.lower().strip() == self.config.flux_err_column.lower()) if has_err else None
                
                for row in reader:
                    time_vals.append(float(row[t_col]))
                    flux_vals.append(float(row[f_col]))
                    if has_err and fe_col:
                        flux_err_vals.append(float(row[fe_col]))
        except Exception as exc:
            raise IngestionError(
                f"Failed to read PLATO synthetic light curve from {source_string!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        time_array = np.array(time_vals)
        flux_array = np.array(flux_vals)
        
        if len(time_array) < 2:
            raise IngestionError("PLATO light curve must contain at least two samples.")
            
        flux_error_list = flux_err_vals if has_err else None

        # Infer cadence basically
        cadence = Cadence.UNKNOWN
        if len(time_array) > 1:
            diffs = np.diff(time_array)
            diffs = diffs[diffs > 0]
            if len(diffs) > 0:
                median_days = np.median(diffs)
                cadence = Cadence.SHORT if median_days <= (5.0 / 1440.0) else Cadence.LONG

        return LightCurve(
            target_id=path.stem,
            mission=Mission.PLATO_SYNTHETIC,
            sector=None,
            cadence=cadence,
            time=time_array.tolist(),
            flux=flux_array.tolist(),
            flux_error=flux_error_list,
            time_unit="days",
            flux_unit="normalized",
            metadata={"source": source_string, "synthetic": True}
        )
