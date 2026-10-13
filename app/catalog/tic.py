from __future__ import annotations

import csv
import gzip
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


# Official TIC v8.1 export:
# headerless CSV/CSV.GZ with exactly 125 columns.
#
# Positions are 1-based and taken directly from the official
# TIC column description.
TIC_V81_COLUMNS = 125

FIELD_POSITIONS = {
    "tic_id": 1,
    "ra_deg": 14,
    "dec_deg": 15,
    "tess_magnitude": 61,
    "teff_k": 65,
    "logg_cgs": 67,
    "metallicity_dex": 69,
    "stellar_radius_solar": 71,
    "stellar_mass_solar": 73,
    "luminosity_solar": 78,
    "distance_pc": 80,
    "priority": 88,
}


@dataclass(frozen=True)
class TicRecord:
    tic_id: str
    ra_deg: float | None = None
    dec_deg: float | None = None
    stellar_radius_solar: float | None = None
    stellar_mass_solar: float | None = None
    teff_k: float | None = None
    luminosity_solar: float | None = None
    logg_cgs: float | None = None
    metallicity_dex: float | None = None
    distance_pc: float | None = None
    tess_magnitude: float | None = None
    priority: float | None = None
    raw: tuple[str, ...] = ()


class TicCatalog:
    """Streaming reader for the real headerless TIC v8.1 CSV/CSV.GZ export."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

        if not self.path.exists():
            raise FileNotFoundError(str(self.path))

    def _open(self):
        if self.path.suffix.lower() == ".gz":
            return gzip.open(
                self.path,
                "rt",
                newline="",
                encoding="utf-8",
            )

        return self.path.open(
            "r",
            newline="",
            encoding="utf-8",
        )

    @staticmethod
    def _number(value: str) -> float | None:
        value = value.strip()

        if value == "":
            return None

        try:
            number = float(value)
        except ValueError as exc:
            raise ValueError(
                f"Invalid numeric TIC value: {value!r}"
            ) from exc

        if not math.isfinite(number):
            return None

        return number

    @staticmethod
    def _field(row: list[str], name: str) -> str:
        position = FIELD_POSITIONS[name]
        return row[position - 1]

    def iter_records(self) -> Iterator[TicRecord]:
        with self._open() as fh:
            reader = csv.reader(fh)

            for line_number, row in enumerate(reader, start=1):
                if not row:
                    continue

                if len(row) != TIC_V81_COLUMNS:
                    raise ValueError(
                        f"TIC v8.1 row {line_number} has "
                        f"{len(row)} columns; expected "
                        f"{TIC_V81_COLUMNS}."
                    )

                tic_id = self._field(row, "tic_id").strip()

                if not tic_id:
                    raise ValueError(
                        f"TIC v8.1 row {line_number} "
                        "has an empty TIC ID."
                    )

                yield TicRecord(
                    tic_id=tic_id,
                    ra_deg=self._number(
                        self._field(row, "ra_deg")
                    ),
                    dec_deg=self._number(
                        self._field(row, "dec_deg")
                    ),
                    stellar_radius_solar=self._number(
                        self._field(row, "stellar_radius_solar")
                    ),
                    stellar_mass_solar=self._number(
                        self._field(row, "stellar_mass_solar")
                    ),
                    teff_k=self._number(
                        self._field(row, "teff_k")
                    ),
                    luminosity_solar=self._number(
                        self._field(row, "luminosity_solar")
                    ),
                    logg_cgs=self._number(
                        self._field(row, "logg_cgs")
                    ),
                    metallicity_dex=self._number(
                        self._field(row, "metallicity_dex")
                    ),
                    distance_pc=self._number(
                        self._field(row, "distance_pc")
                    ),
                    tess_magnitude=self._number(
                        self._field(row, "tess_magnitude")
                    ),
                    priority=self._number(
                        self._field(row, "priority")
                    ),
                    raw=tuple(row),
                )

    def find_tic(self, tic_id: str | int) -> TicRecord | None:
        wanted = str(tic_id).strip()

        if wanted.upper().startswith("TIC"):
            wanted = wanted[3:].strip()

        for record in self.iter_records():
            if record.tic_id == wanted:
                return record

        return None