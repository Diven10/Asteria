from __future__ import annotations

import gzip

import pytest

from app.catalog.tic_ctl import CatalogIngestionError, TicCtlCatalog


CSV = """ticid,ra,dec,rad,mass,teff,lum,logg,mh,d,tmag,priority
123456789,101.5,-20.25,1.1,0.95,5700,1.2,4.4,-0.1,120.0,10.5,0.85
987654321,202.0,30.0,0.8,0.7,4500,0.4,4.6,0.0,80.0,11.2,0.55
"""


def test_find_tic_reads_plain_csv(tmp_path) -> None:
    path = tmp_path / "ctl.csv"
    path.write_text(CSV, encoding="utf-8")

    record = TicCtlCatalog(path).find_tic("TIC 123456789")

    assert record is not None
    assert record.tic_id == "123456789"
    assert record.ra_deg == 101.5
    assert record.dec_deg == -20.25
    assert record.stellar_radius_solar == 1.1
    assert record.stellar_mass_solar == 0.95
    assert record.teff_k == 5700.0
    assert record.ctl_priority == 0.85
    assert record.raw["tmag"] == "10.5"


def test_find_tic_reads_gzip_csv(tmp_path) -> None:
    path = tmp_path / "tic.csv.gz"
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        handle.write(CSV)

    record = TicCtlCatalog(path).find_tic(987654321)

    assert record is not None
    assert record.tic_id == "987654321"
    assert record.distance_pc == 80.0


def test_missing_tic_returns_none(tmp_path) -> None:
    path = tmp_path / "ctl.csv"
    path.write_text(CSV, encoding="utf-8")

    assert TicCtlCatalog(path).find_tic(111111111) is None


def test_missing_tic_column_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("ra,dec\n1,2\n", encoding="utf-8")

    with pytest.raises(CatalogIngestionError, match="TIC identifier"):
        TicCtlCatalog(path).count_rows()


def test_missing_catalog_file_is_rejected(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        TicCtlCatalog(tmp_path / "does_not_exist.csv").count_rows()


def test_bad_numeric_value_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "ticid,teff\n123456789,not-a-number\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogIngestionError, match="numeric"):
        TicCtlCatalog(path).find_tic(123456789)
