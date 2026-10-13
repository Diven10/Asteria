import csv
import gzip
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

class CatalogIngestionError(Exception):
    pass

@dataclass(frozen=True)
class CatalogRecord:
    tic_id: str
    ra_deg: float | None = None
    dec_deg: float | None = None
    stellar_radius_solar: float | None = None
    stellar_mass_solar: float | None = None
    teff_k: float | None = None
    ctl_priority: float | None = None
    distance_pc: float | None = None
    raw: dict[str, str] = field(default_factory=dict)


class TicCtlCatalog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Catalog file not found: {self.path}")

    def _open(self):
        if self.path.suffix.lower() == ".gz":
            return gzip.open(self.path, "rt", encoding="utf-8", newline="")
        return self.path.open("r", encoding="utf-8", newline="")

    def count_rows(self) -> int:
        count = 0
        with self._open() as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or "ticid" not in [c.lower() for c in reader.fieldnames]:
                raise CatalogIngestionError("TIC identifier column not found")
            for _ in reader:
                count += 1
        return count

    def find_tic(self, tic_id: str | int) -> CatalogRecord | None:
        wanted = str(tic_id).strip()
        if wanted.upper().startswith("TIC"):
            wanted = wanted[3:].strip()

        with self._open() as fh:
            reader = csv.DictReader(fh)
            fieldnames = [c.lower() for c in (reader.fieldnames or [])]
            if "ticid" not in fieldnames:
                raise CatalogIngestionError("TIC identifier column not found")
            
            for row in reader:
                row_lower = {k.lower(): v for k, v in row.items()}
                if row_lower.get("ticid", "").strip() == wanted:
                    try:
                        def parse_float(key: str) -> float | None:
                            val = row_lower.get(key, "").strip()
                            if not val:
                                return None
                            return float(val)
                        
                        return CatalogRecord(
                            tic_id=wanted,
                            ra_deg=parse_float("ra"),
                            dec_deg=parse_float("dec"),
                            stellar_radius_solar=parse_float("rad"),
                            stellar_mass_solar=parse_float("mass"),
                            teff_k=parse_float("teff"),
                            ctl_priority=parse_float("priority"),
                            distance_pc=parse_float("d"),
                            raw=row
                        )
                    except ValueError as e:
                        raise CatalogIngestionError(f"Invalid numeric value: {e}") from e

        return None