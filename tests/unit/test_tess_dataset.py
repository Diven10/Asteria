import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch

from app.contracts.models import LightCurve, Mission, Cadence
from app.ml.dataset_builder import AuthoritativeTarget
from app.ml.tess_dataset import TESSAcquisitionLayer
from app.ingestion.service import IngestionService

@pytest.fixture
def mock_ingestion_service():
    service = MagicMock(spec=IngestionService)
    # Default successful return
    service.download_tess.return_value = LightCurve(
        target_id="123", mission=Mission.TESS, sector=1, cadence=Cadence.SHORT,
        time=[1.0, 2.0], flux=[1.0, 1.0], flux_error=[0.01, 0.01],
        time_unit="days", flux_unit="normalized", metadata={}
    )
    return service

def test_successful_lookup_and_download(mock_ingestion_service):
    # 1. successful lookup & 2. successful download
    with tempfile.TemporaryDirectory() as tmpdir:
        layer = TESSAcquisitionLayer(mock_ingestion_service, download_dir=tmpdir)
        target = AuthoritativeTarget(
            target_id="123", mission=Mission.TESS, authoritative_label=1, host_star_id="123", sector=1
        )
        
        lc = layer.ingest(target)
        
        assert lc.target_id == "123"
        assert lc.sector == 1
        
        # Verify call to underlying ingestion service
        mock_ingestion_service.download_tess.assert_called_once_with(
            "TIC 123", sector=1, download_dir=tmpdir
        )
        
        # Verify provenance
        assert len(layer.acquisition_log) == 1
        log = layer.acquisition_log[0]
        assert log["acquisition_status"] == "SUCCESS"
        assert log["tic_id"] == "123"
        assert log["sector"] == 1
        assert log["local_cache_path"] == tmpdir
        assert log["error"] is None

@patch("lightkurve.search_lightcurve")
def test_missing_sector_resolves_deterministically(mock_search, mock_ingestion_service):
    # 5. multiple observations
    mock_search_result = MagicMock()
    mock_search_result.sector = [4, 2, 6]  # Multiple sectors
    mock_search_result.__len__.return_value = 3
    mock_search.return_value = mock_search_result
    
    layer = TESSAcquisitionLayer(mock_ingestion_service)
    target = AuthoritativeTarget(
        target_id="456", mission=Mission.TESS, authoritative_label=0, host_star_id="456", sector=None
    )
    
    lc = layer.ingest(target)
    
    # Should resolve to the minimum sector: 2
    mock_search.assert_called_once_with("TIC 456", mission="TESS", author="SPOC")
    mock_ingestion_service.download_tess.assert_called_once_with(
        "TIC 456", sector=2, download_dir=None
    )
    assert layer.acquisition_log[0]["sector"] == 2

@patch("lightkurve.search_lightcurve")
def test_missing_target_fails_gracefully(mock_search, mock_ingestion_service):
    # 3. missing target
    mock_search_result = MagicMock()
    mock_search_result.__len__.return_value = 0 # No results
    mock_search.return_value = mock_search_result
    
    layer = TESSAcquisitionLayer(mock_ingestion_service)
    target = AuthoritativeTarget(
        target_id="789", mission=Mission.TESS, authoritative_label=0, host_star_id="789", sector=None
    )
    
    with pytest.raises(ValueError, match="No TESS sectors found"):
        layer.ingest(target)
        
    assert layer.acquisition_log[0]["acquisition_status"] == "FAILED"
    assert layer.acquisition_log[0]["failure_stage"] == "acquisition"

def test_download_failure_recorded(mock_ingestion_service):
    # 6. download failure & 8. malformed observation
    mock_ingestion_service.download_tess.side_effect = RuntimeError("MAST API is down")
    
    layer = TESSAcquisitionLayer(mock_ingestion_service)
    target = AuthoritativeTarget(
        target_id="999", mission=Mission.TESS, authoritative_label=1, host_star_id="999", sector=1
    )
    
    with pytest.raises(RuntimeError, match="MAST API is down"):
        layer.ingest(target)
        
    assert layer.acquisition_log[0]["acquisition_status"] == "FAILED"
    assert "MAST API is down" in layer.acquisition_log[0]["error"]

def test_cached_observation(mock_ingestion_service):
    # 7. cached observation - existing ingestion service handles this natively,
    # we just need to ensure the layer propagates the call correctly
    layer = TESSAcquisitionLayer(mock_ingestion_service, download_dir="/cached/dir")
    target = AuthoritativeTarget(
        target_id="123", mission=Mission.TESS, authoritative_label=1, host_star_id="123", sector=1
    )
    
    lc = layer.ingest(target)
    mock_ingestion_service.download_tess.assert_called_once_with(
        "TIC 123", sector=1, download_dir="/cached/dir"
    )
    assert layer.acquisition_log[0]["local_cache_path"] == "/cached/dir"
