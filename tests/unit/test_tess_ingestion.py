from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import numpy as np
import pytest

from app.contracts.models import Cadence, Mission
from app.ingestion.base import IngestionError
from app.ingestion.tess import TessIngestor, _to_contract


class FakeTessLightCurve:
    mission = "TESS"
    targetid = 123456789
    label = "TIC 123456789"
    sector = 42
    camera = 3
    ccd = 2
    ra = 100.25
    dec = -20.5
    time_format = "btjd"
    meta = {
        "TICID": 123456789,
        "SECTOR": 42,
        "AUTHOR": "SPOC",
        "RA_OBJ": 100.25,
        "DEC_OBJ": -20.5,
    }

    def __init__(self) -> None:
        self.time = np.array([2000.0, 2000.00138889, 2000.00277778])
        self.flux = np.array([1000.0, 999.0, 1001.0])
        self.flux_err = np.array([2.0, 2.0, 2.0])


def test_to_contract_maps_tess_lightcurve() -> None:
    result = _to_contract(
        FakeTessLightCurve(),
        source="/tmp/example_lc.fits",
        config=SimpleNamespace(flux_column="pdcsap_flux", quality_bitmask="default"),
    )
    assert isinstance(result.light_curve_id, UUID)
    assert result.target_id == "123456789"
    assert result.mission is Mission.TESS
    assert result.sector == 42
    assert result.cadence is Cadence.SHORT
    assert result.time_unit == "btjd"


def test_ingest_file_rejects_missing_local_file() -> None:
    with pytest.raises(FileNotFoundError):
        TessIngestor().ingest_file("/definitely/not/a/real/tess_file.fits")


def test_to_contract_rejects_non_tess_data() -> None:
    native = FakeTessLightCurve()
    native.mission = "KEPLER"
    with pytest.raises(IngestionError, match="non-TESS"):
        _to_contract(
            native,
            source="/tmp/example.fits",
            config=SimpleNamespace(flux_column="pdcsap_flux", quality_bitmask="default"),
        )


def test_to_contract_rejects_mismatched_lengths() -> None:
    native = FakeTessLightCurve()
    native.flux = np.array([1.0, 2.0])
    with pytest.raises(IngestionError, match="equal lengths"):
        _to_contract(
            native,
            source="/tmp/example.fits",
            config=SimpleNamespace(flux_column="pdcsap_flux", quality_bitmask="default"),
        )


def test_ingest_file_uses_lightkurve_reader(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    native = FakeTessLightCurve()
    source = tmp_path / "tess_example_lc.fits"
    source.write_bytes(b"synthetic test placeholder")

    class FakeLightkurve:
        def read(self, path, **kwargs):
            assert path == str(source)
            assert kwargs["flux_column"] == "pdcsap_flux"
            assert kwargs["quality_bitmask"] == "default"
            return native

    monkeypatch.setattr("app.ingestion.tess._load_lightkurve", lambda: FakeLightkurve())
    result = TessIngestor().ingest_file(source)
    assert result.target_id == "123456789"


def test_search_and_download_uses_exactly_one_product(monkeypatch: pytest.MonkeyPatch) -> None:
    native = FakeTessLightCurve()

    class FakeProduct:
        def download(self, **kwargs):
            assert kwargs["quality_bitmask"] == "default"
            return native

    class FakeResults:
        author = ["SPOC"]
        sector = [42]
        exptime = [SimpleNamespace(value=120)]

        def __len__(self) -> int:
            return 1

        def __getitem__(self, index: int):
            return FakeProduct()

    class FakeLightkurve:
        def search_lightcurve(self, target, **kwargs):
            assert target == "TIC 123456789"
            assert kwargs["mission"] == "TESS"
            assert kwargs["sector"] == 42
            return FakeResults()

    monkeypatch.setattr("app.ingestion.tess._load_lightkurve", lambda: FakeLightkurve())
    result = TessIngestor().search_and_download("TIC 123456789", sector=42)
    assert result.target_id == "123456789"
    assert result.metadata["archive"]["exptime_seconds"] == 120.0


def test_search_and_download_rejects_ambiguous_results(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResults:
        def __len__(self) -> int:
            return 2

    class FakeLightkurve:
        def search_lightcurve(self, target, **kwargs):
            return FakeResults()

    monkeypatch.setattr("app.ingestion.tess._load_lightkurve", lambda: FakeLightkurve())
    with pytest.raises(IngestionError, match="returned 2 products"):
        TessIngestor().search_and_download("TIC 123456789")
