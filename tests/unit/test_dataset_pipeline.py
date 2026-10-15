"""Unit tests for the TESS dataset generation and auditing pipeline."""

import json
import os
import tempfile
import numpy as np
import pandas as pd
import pytest

from app.contracts.models import Cadence, LightCurve, Mission
from app.features.engineering import CANONICAL_FEATURES, FEATURE_SCHEMA_VERSION
from app.ml.authoritative_data import AuthoritativeTOICandidate
from app.ml.dataset_builder import AuthoritativeTarget
from app.ml.tess_dataset_pipeline import (
    DatasetPipelineConfig,
    TESSDatasetPipeline,
    compute_file_sha256,
)


class MockAcquisitionLayer:
    """Mock acquisition layer providing controlled synthetic light curves for test fixtures."""

    def __init__(self):
        self.light_curves = {}

    def set_mock_curve(self, target_id: str, lc: LightCurve):
        self.light_curves[str(target_id)] = lc

    def ingest(self, target: AuthoritativeTarget) -> LightCurve:
        tid = str(target.target_id)
        if tid in self.light_curves:
            return self.light_curves[tid]
        raise ValueError(f"No mock light curve for target {tid}")


def _create_mock_lc(
    target_id: str,
    period: float = 4.0,
    duration: float = 0.2,
    epoch: float = 1.0,
    depth: float = 0.01,
    n_days: float = 20.0,
    n_points: int = 2000,
) -> LightCurve:
    time = np.linspace(0, n_days, n_points)
    flux = np.ones_like(time)
    phase = (time - epoch + 0.5 * period) % period - 0.5 * period
    flux[np.abs(phase) < 0.5 * duration] -= depth

    return LightCurve(
        target_id=f"TIC {target_id}",
        mission=Mission.TESS,
        sector=1,
        cadence=Cadence.SHORT,
        time=time.tolist(),
        flux=flux.tolist(),
        flux_error=(np.ones_like(time) * 0.0001).tolist(),
        time_unit="days",
        flux_unit="normalized",
    )


def test_pipeline_label_mapping_and_signal_matching():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetPipelineConfig(
            output_dir=tmpdir,
            min_period=1.0,
            max_period=10.0,
            period_tolerance=0.03,
            max_phase_offset=0.05,
        )
        mock_acq = MockAcquisitionLayer()
        pipeline = TESSDatasetPipeline(config=config, acquisition_layer=mock_acq)

        # 1. Target 101: Confirmed Planet (CP), matched signal
        lc101 = _create_mock_lc("101", period=4.0, epoch=1.0, depth=0.01)
        mock_acq.set_mock_curve("101", lc101)
        target101 = AuthoritativeTarget(
            target_id="101",
            mission=Mission.TESS,
            authoritative_label=1,
            host_star_id="101",
            sector=1,
            candidates=[
                AuthoritativeTOICandidate(
                    toi_id="101.01",
                    tic_id="101",
                    disposition="CP",
                    supervised_label=1,
                    period_days=4.001,
                    epoch_bjd=2457001.0,  # BTJD = 1.0
                    duration_hours=4.8,
                    depth_ppm=10000.0,
                    stellar_radius=1.0,
                    stellar_teff=5778.0,
                )
            ],
        )

        # 2. Target 202: False Positive (FP), matched signal
        lc202 = _create_mock_lc("202", period=3.0, epoch=0.5, depth=0.02)
        mock_acq.set_mock_curve("202", lc202)
        target202 = AuthoritativeTarget(
            target_id="202",
            mission=Mission.TESS,
            authoritative_label=0,
            host_star_id="202",
            sector=1,
            candidates=[
                AuthoritativeTOICandidate(
                    toi_id="202.01",
                    tic_id="202",
                    disposition="FP",
                    supervised_label=0,
                    period_days=3.002,
                    epoch_bjd=2457000.5,  # BTJD = 0.5
                    duration_hours=4.8,
                    depth_ppm=20000.0,
                    stellar_radius=1.2,
                    stellar_teff=6200.0,
                )
            ],
        )

        # 3. Target 303: Ambiguous Candidate (PC) -> Excluded from supervised dataset
        lc303 = _create_mock_lc("303", period=5.0, epoch=2.0, depth=0.005)
        mock_acq.set_mock_curve("303", lc303)
        target303 = AuthoritativeTarget(
            target_id="303",
            mission=Mission.TESS,
            authoritative_label=None,
            host_star_id="303",
            sector=1,
            candidates=[
                AuthoritativeTOICandidate(
                    toi_id="303.01",
                    tic_id="303",
                    disposition="PC",
                    supervised_label=None,
                    period_days=5.001,
                    epoch_bjd=2457002.0,
                    duration_hours=4.8,
                    depth_ppm=5000.0,
                )
            ],
        )

        # 4. Target 404: Confirmed Planet target, but light curve exhibits an UNMATCHED period
        # Light curve has P=7.5 d, but catalog candidate is P=2.5 d -> Must NOT be given label 1!
        lc404 = _create_mock_lc("404", period=7.5, epoch=1.0, depth=0.01)
        mock_acq.set_mock_curve("404", lc404)
        target404 = AuthoritativeTarget(
            target_id="404",
            mission=Mission.TESS,
            authoritative_label=1,
            host_star_id="404",
            sector=1,
            candidates=[
                AuthoritativeTOICandidate(
                    toi_id="404.01",
                    tic_id="404",
                    disposition="CP",
                    supervised_label=1,
                    period_days=2.500,  # Unmatched!
                    epoch_bjd=2457001.0,
                    duration_hours=2.0,
                    depth_ppm=10000.0,
                )
            ],
        )

        df, manifest, audit = pipeline.run_pipeline(targets=[target101, target202, target303, target404])

        # Assert only matched CP and FP are in the supervised dataset
        assert len(df) == 2
        assert set(df["label"].unique()) == {0, 1}

        # Check positive candidate (101.01)
        row101 = df[df["target_id"] == "101"].iloc[0]
        assert row101["label"] == 1
        assert row101["toi_id"] == "101.01"
        assert row101["match_status"] == "DIRECT_MATCH"

        # Check negative candidate (202.01)
        row202 = df[df["target_id"] == "202"].iloc[0]
        assert row202["label"] == 0
        assert row202["toi_id"] == "202.01"
        assert row202["match_status"] == "DIRECT_MATCH"

        # Verify Target 404 (unmatched) was EXCLUDED and NOT assigned label 1
        assert "404" not in df["target_id"].values
        rec404 = next(r for r in manifest["records"] if r["tic_id"] == "404")
        assert rec404["is_supervised"] is False
        assert "UNMATCHED_PERIOD" in rec404["matching"]["match_status"]
        assert rec404["supervised_label"] is None

        # Verify Target 303 (ambiguous PC) was EXCLUDED
        assert "303" not in df["target_id"].values
        rec303 = next(r for r in manifest["records"] if r["tic_id"] == "303")
        assert rec303["is_supervised"] is False
        assert "ambiguous disposition" in rec303["exclusion_reason"]


def test_pipeline_schema_2_features_and_provenance_manifest():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatasetPipelineConfig(output_dir=tmpdir, min_period=1.0, max_period=10.0)
        mock_acq = MockAcquisitionLayer()
        pipeline = TESSDatasetPipeline(config=config, acquisition_layer=mock_acq)

        lc = _create_mock_lc("999", period=4.0, epoch=1.0, depth=0.01)
        mock_acq.set_mock_curve("999", lc)
        target = AuthoritativeTarget(
            target_id="999",
            mission=Mission.TESS,
            authoritative_label=1,
            host_star_id="999",
            sector=1,
            candidates=[
                AuthoritativeTOICandidate(
                    toi_id="999.01",
                    tic_id="999",
                    disposition="CP",
                    supervised_label=1,
                    period_days=4.0,
                    epoch_bjd=2457001.0,
                    duration_hours=4.8,
                    depth_ppm=10000.0,
                    stellar_radius=1.0,
                    stellar_teff=5778.0,
                )
            ],
        )

        df, manifest, audit = pipeline.run_pipeline(targets=[target])

        # Verify Schema 2.0
        assert manifest["feature_schema_version"] == "2.0"
        assert manifest["feature_schema_version"] == FEATURE_SCHEMA_VERSION

        # Verify all 13 canonical features are in DataFrame
        for col in CANONICAL_FEATURES:
            assert col in df.columns
        assert "secondary_eclipse_depth" in df.columns

        # Verify persisted files
        csv_file = os.path.join(tmpdir, "features.csv")
        manifest_file = os.path.join(tmpdir, "manifest.json")

        assert os.path.exists(csv_file)
        assert os.path.exists(manifest_file)

        # Verify SHA-256 Checksums match
        assert manifest["checksums"]["features_csv_sha256"] == compute_file_sha256(csv_file)

        parquet_file = os.path.join(tmpdir, "features.parquet")
        if os.path.exists(parquet_file):
            assert manifest["checksums"]["features_parquet_sha256"] == compute_file_sha256(parquet_file)

        # Reload manifest
        with open(manifest_file, "r") as f:
            loaded_manifest = json.load(f)
        assert loaded_manifest["manifest_version"] == "2.0"
        assert loaded_manifest["dataset_summary"]["supervised_samples_approved"] == 1

