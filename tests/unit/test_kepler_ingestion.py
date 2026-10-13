from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import numpy as np
import pytest

from app.contracts.models import Cadence, Mission
from app.ingestion.base import IngestionError
from app.ingestion.kepler import KeplerIngestor, _to_contract, KeplerIngestionConfig


class FakeKeplerLightCurve:
    mission = "KEPLER"
    targetid = 123456789
    label = "KIC 123456789"
    quarter = 4
    module = 3
    channel = 2
    ra = 100.25
    dec = -20.5
    time_format = "bkjd"
    meta = {
        "KEPLERID": 123456789,
        "QUARTER": 4,
        "AUTHOR": "Kepler",
        "RA_OBJ": 100.25,
        "DEC_OBJ": -20.5,
    }

    def __init__(self) -> None:
        self.time = np.array([2000.0, 2000.02, 2000.04])
        self.flux = np.array([1000.0, 999.0, 1001.0])
        self.flux_err = np.array([2.0, 2.0, 2.0])


def test_to_contract_maps_kepler_lightcurve() -> None:
    result = _to_contract(
        FakeKeplerLightCurve(),
        source="/tmp/example_lc.fits",
        config=KeplerIngestionConfig(),
    )
    assert isinstance(result.light_curve_id, UUID)
    assert result.target_id == "123456789"
    assert result.mission is Mission.KEPLER
    assert result.sector == 4  # Maps from quarter
    assert result.cadence is Cadence.LONG  # Based on roughly 30m cadence
    assert result.time_unit == "bkjd"


def test_to_contract_maps_k2_lightcurve() -> None:
    lc = FakeKeplerLightCurve()
    lc.mission = "K2"
    lc.quarter = None
    lc.campaign = 5
    lc.meta["CAMPAIGN"] = 5
    result = _to_contract(
        lc,
        source="/tmp/k2_example.fits",
        config=KeplerIngestionConfig(),
    )
    assert result.mission is Mission.KEPLER
    assert result.sector == 5  # Maps from campaign


def test_ingest_file_rejects_missing_local_file() -> None:
    with pytest.raises(FileNotFoundError):
        KeplerIngestor().ingest_file("/definitely/not/a/real/kepler_file.fits")


def test_to_contract_rejects_non_kepler_data() -> None:
    native = FakeKeplerLightCurve()
    native.mission = "TESS"
    with pytest.raises(IngestionError, match="non-Kepler/K2"):
        _to_contract(
            native,
            source="/tmp/example.fits",
            config=KeplerIngestionConfig(),
        )


def test_ingest_file_uses_lightkurve_reader(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    native = FakeKeplerLightCurve()
    source = tmp_path / "kepler_example_lc.fits"
    source.write_bytes(b"synthetic test placeholder")

    class FakeLightkurve:
        def read(self, path, **kwargs):
            assert path == str(source)
            assert kwargs["flux_column"] == "pdcsap_flux"
            return native

    monkeypatch.setattr("app.ingestion.kepler._load_lightkurve", lambda: FakeLightkurve())
    result = KeplerIngestor().ingest_file(source)
    assert result.target_id == "123456789"


def test_search_and_download_uses_exactly_one_product(monkeypatch: pytest.MonkeyPatch) -> None:
    native = FakeKeplerLightCurve()

    class FakeProduct:
        def download(self, **kwargs):
            return native

    class FakeResults:
        author = ["Kepler"]
        quarter = [4]
        exptime = [SimpleNamespace(value=1800)]

        def __len__(self) -> int:
            return 1

        def __getitem__(self, index: int):
            return FakeProduct()

    class FakeLightkurve:
        def search_lightcurve(self, target, **kwargs):
            assert target == "KIC 123456789"
            assert kwargs["mission"] == ("Kepler", "K2")
            assert kwargs["quarter"] == 4
            return FakeResults()

    monkeypatch.setattr("app.ingestion.kepler._load_lightkurve", lambda: FakeLightkurve())
    result = KeplerIngestor().search_and_download("KIC 123456789", quarter=4)
    assert result.target_id == "123456789"
    assert result.metadata["archive"]["quarter"] == 4
