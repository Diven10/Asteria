from pathlib import Path

import pytest

from app.catalog.tic import (
    FIELD_POSITIONS,
    TIC_V81_COLUMNS,
    TicCatalog,
)


def make_row(**overrides: str) -> list[str]:
    row = [""] * TIC_V81_COLUMNS

    values = {
        "tic_id": "334299896",
        "ra_deg": "80.252507971295302",
        "dec_deg": "89.098606827092397",
        "tess_magnitude": "16.454",
        "teff_k": "3335.0",
        "logg_cgs": "4.3323901",
        "metallicity_dex": "0.0108723",
        "stellar_radius_solar": "0.043519299",
        "stellar_mass_solar": "0.045",
        "luminosity_solar": "0.001",
        "distance_pc": "92.5",
        "priority": "0.0001",
    }

    values.update(overrides)

    for name, value in values.items():
        row[FIELD_POSITIONS[name] - 1] = value

    return row


def test_reads_headerless_tic_csv(tmp_path: Path):
    path = tmp_path / "tic.csv"
    path.write_text(
        ",".join(make_row()) + "\n",
        encoding="utf-8",
    )

    record = next(TicCatalog(path).iter_records())

    assert record.tic_id == "334299896"
    assert record.ra_deg == pytest.approx(
        80.252507971295302
    )
    assert record.dec_deg == pytest.approx(
        89.098606827092397
    )
    assert record.tess_magnitude == pytest.approx(16.454)
    assert record.teff_k == pytest.approx(3335.0)


def test_reads_gzip_tic(tmp_path: Path):
    import gzip

    path = tmp_path / "tic.csv.gz"

    with gzip.open(
        path,
        "wt",
        encoding="utf-8",
        newline="",
    ) as fh:
        fh.write(",".join(make_row()) + "\n")

    record = TicCatalog(path).find_tic(
        "TIC 334299896"
    )

    assert record is not None
    assert record.tic_id == "334299896"


def test_rejects_wrong_column_count(tmp_path: Path):
    path = tmp_path / "bad.csv"

    path.write_text(
        "1,2,3\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="expected 125",
    ):
        next(TicCatalog(path).iter_records())


def test_preserves_raw_row(tmp_path: Path):
    row = make_row()

    path = tmp_path / "tic.csv"

    path.write_text(
        ",".join(row) + "\n",
        encoding="utf-8",
    )

    record = next(
        TicCatalog(path).iter_records()
    )

    assert len(record.raw) == 125
    assert record.raw[0] == "334299896"


def test_empty_numeric_fields_become_none(
    tmp_path: Path,
):
    row = make_row(
        teff_k="",
        stellar_mass_solar="",
    )

    path = tmp_path / "tic.csv"

    path.write_text(
        ",".join(row) + "\n",
        encoding="utf-8",
    )

    record = next(
        TicCatalog(path).iter_records()
    )

    assert record.teff_k is None
    assert record.stellar_mass_solar is None
