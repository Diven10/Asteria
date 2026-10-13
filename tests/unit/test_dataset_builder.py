import pytest
import numpy as np
import pandas as pd
import json
import os
import tempfile
from typing import List

from app.contracts.models import LightCurve, Mission, Cadence, DetectionCandidate
from app.ml.dataset_builder import (
    DatasetBuilder,
    AuthoritativeTarget,
    BuilderConfig,
    IngestionInterface,
    select_highest_bls_power
)
from app.features.engineering import FEATURE_SCHEMA_VERSION

class MockIngestionService(IngestionInterface):
    """Mocks ingestion to prevent network calls during unit tests."""
    
    def __init__(self, simulate_failure_for: List[str] = None, simulate_empty_for: List[str] = None):
        self.simulate_failure_for = simulate_failure_for or []
        self.simulate_empty_for = simulate_empty_for or []

    def ingest(self, target: AuthoritativeTarget) -> LightCurve:
        if target.target_id in self.simulate_failure_for:
            raise RuntimeError("Mock network failure")

        time = np.linspace(0, 10, 500)
        flux = np.ones(500)
        
        # Inject a transit so BLS finds something, unless simulate_empty_for is set
        if target.target_id not in self.simulate_empty_for:
            transit_mask = ((time % 2.5) > 1.0) & ((time % 2.5) < 1.1)
            flux[transit_mask] -= 0.05

        return LightCurve(
            target_id=target.target_id,
            mission=target.mission,
            sector=target.sector,
            cadence=Cadence.SHORT,
            time=time.tolist(),
            flux=flux.tolist(),
            flux_error=(np.ones(500) * 0.001).tolist(),
            time_unit="days",
            flux_unit="normalized",
            metadata={}
        )

@pytest.fixture
def mock_ingestion():
    return MockIngestionService()

def test_dataset_builder_deterministic_generation(mock_ingestion):
    builder = DatasetBuilder(ingestion_service=mock_ingestion)
    
    targets = [
        AuthoritativeTarget(target_id="T1", mission=Mission.TESS, authoritative_label=1, host_star_id="H1", sector=1, provenance="NASA_EA"),
        AuthoritativeTarget(target_id="T2", mission=Mission.TESS, authoritative_label=0, host_star_id="H2", sector=1, provenance="NASA_EA")
    ]
    
    df, metadata, failures = builder.build(targets)
    
    assert len(failures) == 0
    assert len(df) == 2
    assert metadata["target_count"] == 2
    assert metadata["successful_count"] == 2
    assert metadata["failed_count"] == 0
    assert metadata["feature_schema_version"] == FEATURE_SCHEMA_VERSION

def test_dataset_builder_preserves_labels_and_groups(mock_ingestion):
    builder = DatasetBuilder(ingestion_service=mock_ingestion)
    
    targets = [
        AuthoritativeTarget(target_id="T1", mission=Mission.TESS, authoritative_label=1, host_star_id="GROUP_A"),
        AuthoritativeTarget(target_id="T2", mission=Mission.TESS, authoritative_label=0, host_star_id="GROUP_B")
    ]
    
    df, metadata, failures = builder.build(targets)
    
    # 3. label preservation
    assert df.loc[df["target_id"] == "T1", "authoritative_label"].iloc[0] == 1
    assert df.loc[df["target_id"] == "T2", "authoritative_label"].iloc[0] == 0
    
    # 4. host-star group preservation
    assert df.loc[df["target_id"] == "T1", "host_star_id"].iloc[0] == "GROUP_A"
    assert df.loc[df["target_id"] == "T2", "host_star_id"].iloc[0] == "GROUP_B"
    
def test_dataset_builder_schema(mock_ingestion):
    builder = DatasetBuilder(ingestion_service=mock_ingestion)
    
    targets = [
        AuthoritativeTarget(target_id="T1", mission=Mission.TESS, authoritative_label=1, host_star_id="H1")
    ]
    
    df, metadata, failures = builder.build(targets)
    
    # 2. correct columns/schema
    assert "target_id" in df.columns
    assert "mission" in df.columns
    assert "authoritative_label" in df.columns
    assert "host_star_id" in df.columns
    assert "bls_power" in df.columns  # one of the extracted features
    assert "snr" in df.columns

def test_missing_label_rejection(mock_ingestion):
    builder = DatasetBuilder(ingestion_service=mock_ingestion, config=BuilderConfig(fail_fast=False))
    
    targets = [
        AuthoritativeTarget(target_id="T1", mission=Mission.TESS, authoritative_label=None, host_star_id="H1")
    ]
    
    df, metadata, failures = builder.build(targets)
    
    # 7. missing label rejection
    assert len(df) == 0
    assert len(failures) == 1
    assert failures[0]["stage"] == "validation"
    assert "Missing authoritative label" in failures[0]["error"]

def test_missing_host_star_handling(mock_ingestion):
    builder = DatasetBuilder(ingestion_service=mock_ingestion, config=BuilderConfig(fail_fast=False))
    
    targets = [
        AuthoritativeTarget(target_id="T1", mission=Mission.TESS, authoritative_label=1, host_star_id="")
    ]
    
    df, metadata, failures = builder.build(targets)
    
    # 8. missing host-star handling
    assert len(df) == 0
    assert len(failures) == 1
    assert failures[0]["stage"] == "validation"
    assert "Missing host_star_id" in failures[0]["error"]

def test_failed_target_handling():
    # Inject a failure for T2
    ingestion = MockIngestionService(simulate_failure_for=["T2"], simulate_empty_for=["T3"])
    def custom_selector(cands):
        if cands and cands[0].target_id == "T3": return None
        return select_highest_bls_power(cands)
        
    builder = DatasetBuilder(ingestion_service=ingestion, config=BuilderConfig(fail_fast=False), candidate_selector=custom_selector)
    
    targets = [
        AuthoritativeTarget(target_id="T1", mission=Mission.TESS, authoritative_label=1, host_star_id="H1"),
        AuthoritativeTarget(target_id="T2", mission=Mission.TESS, authoritative_label=1, host_star_id="H2"),
        AuthoritativeTarget(target_id="T3", mission=Mission.TESS, authoritative_label=1, host_star_id="H3"),
    ]
    
    df, metadata, failures = builder.build(targets)
    
    # 9. failed target handling
    assert len(df) == 1  # Only T1 succeeds
    assert df["target_id"].iloc[0] == "T1"
    
    assert len(failures) == 2
    f_t2 = next(f for f in failures if f["target_id"] == "T2")
    assert f_t2["stage"] == "execution"
    assert "Mock network failure" in f_t2["error"]
    
    f_t3 = next(f for f in failures if f["target_id"] == "T3")
    assert f_t3["stage"] == "detection"
    assert "No BLS candidates detected" in f_t3["error"]

def test_fail_fast_behavior():
    ingestion = MockIngestionService(simulate_failure_for=["T2"])
    builder = DatasetBuilder(ingestion_service=ingestion, config=BuilderConfig(fail_fast=True))
    
    targets = [
        AuthoritativeTarget(target_id="T1", mission=Mission.TESS, authoritative_label=1, host_star_id="H1"),
        AuthoritativeTarget(target_id="T2", mission=Mission.TESS, authoritative_label=1, host_star_id="H2"),
    ]
    
    with pytest.raises(RuntimeError, match="Mock network failure"):
        builder.build(targets)

def test_persistence_and_reload(mock_ingestion):
    builder = DatasetBuilder(ingestion_service=mock_ingestion)
    
    targets = [
        AuthoritativeTarget(target_id="T1", mission=Mission.TESS, authoritative_label=1, host_star_id="H1", sector=1, provenance="NASA_EA")
    ]
    
    df, metadata, failures = builder.build(targets)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "dataset.csv")
        meta_path = os.path.join(tmpdir, "metadata.json")
        
        # 10. persistence and reload
        builder.save_csv(df, metadata, csv_path, meta_path)
        
        # Verify reload
        reloaded_df = pd.read_csv(csv_path)
        assert len(reloaded_df) == 1
        assert reloaded_df["target_id"].iloc[0] == "T1"
        assert reloaded_df["authoritative_label"].iloc[0] == 1
        
        with open(meta_path, "r") as f:
            reloaded_meta = json.load(f)
            
        assert reloaded_meta["successful_count"] == 1
        assert reloaded_meta["feature_schema_version"] == FEATURE_SCHEMA_VERSION

def test_candidate_selection_determinism():
    # 6. candidate selection determinism
    # Test our default strategy picks the max bls_power
    from app.contracts.models import DetectionCandidate
    from uuid import uuid4
    c1 = DetectionCandidate(
        candidate_id=str(uuid4()), light_curve_id=str(uuid4()),
        target_id="T1", mission=Mission.TESS, period_days=1.0, epoch_btjd=1.0,
        duration_hours=1.0, depth=0.01, bls_power=10.0, snr=5.0, transit_count=3,
        metadata={}
    )
    c2 = DetectionCandidate(
        candidate_id=str(uuid4()), light_curve_id=str(uuid4()),
        target_id="T1", mission=Mission.TESS, period_days=2.0, epoch_btjd=2.0,
        duration_hours=1.0, depth=0.01, bls_power=20.0, snr=5.0, transit_count=3,
        metadata={}
    )
    
    best = select_highest_bls_power([c1, c2])
    assert best == c2
    
    # Custom strategy testing
    def select_lowest_period(cands):
        return min(cands, key=lambda c: c.period_days)
        
    builder = DatasetBuilder(
        ingestion_service=MockIngestionService(), 
        candidate_selector=select_lowest_period
    )
    assert builder.candidate_selector([c1, c2]) == c1
