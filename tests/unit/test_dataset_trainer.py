import os
import tempfile
import numpy as np
import pandas as pd
import pytest
from app.contracts.models import DetectionCandidate, Mission
from app.features.engineering import FEATURE_SCHEMA_VERSION
from app.ml.classifier import ExoplanetClassifier
from app.ml.dataset_trainer import (
    CANONICAL_FEATURES,
    DatasetTrainerConfig,
    DatasetValidationError,
    IncompatibleDatasetError,
    train_from_dataset,
    validate_and_load_dataset,
)


def _create_mock_dataset(filepath: str, n_records: int = 100, n_targets: int = 15):
    """Creates a mock astronomical feature dataset for testing."""
    records = []
    rng = np.random.RandomState(42)

    for i in range(n_records):
        target_id = f"TIC_{i % n_targets}"
        is_planet = (i % 2 == 0)
        disp = "CP" if is_planet else "FP"

        period = float(rng.uniform(1.0, 15.0))
        duration = float(rng.uniform(1.0, 4.0))
        depth = float(rng.uniform(0.005, 0.02)) if is_planet else float(rng.uniform(0.0001, 0.001))
        bls_power = float(rng.uniform(80.0, 300.0)) if is_planet else float(rng.uniform(5.0, 30.0))
        snr = float(rng.uniform(10.0, 40.0)) if is_planet else float(rng.uniform(1.0, 5.0))

        row = {
            "target_id": target_id,
            "host_star_id": target_id,
            "disposition": disp,
            "period_days": period,
            "duration_hours": duration,
            "depth": depth,
            "bls_power": bls_power,
            "snr": snr,
            "transit_count": 5,
            "odd_even_depth_difference": 0.0001,
            "secondary_eclipse_power": 0.0001,
            "stellar_radius_solar": 1.0,
            "stellar_mass_solar": 1.0,
            "stellar_teff_k": 5778.0,
            "depth_scaled": depth,
            "semi_major_axis_au": 0.05,
        }
        records.append(row)

    df = pd.DataFrame(records)
    df.to_csv(filepath, index=False)
    return df


def test_dataset_trainer_rejects_incompatible_ctl():
    with tempfile.TemporaryDirectory() as tmpdir:
        ctl_path = os.path.join(tmpdir, "exo_CTL_08.01.csv")
        with open(ctl_path, "w") as f:
            f.write("80423805,1.923E-4,planetcandidate,80\n")
            f.write("80423930,9.996E-5,cooldwarfs_v8,92\n")

        cfg = DatasetTrainerConfig(data_path=ctl_path)
        with pytest.raises(IncompatibleDatasetError, match="TESS Candidate Target List"):
            validate_and_load_dataset(cfg)


def test_dataset_trainer_rejects_missing_features():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "invalid.csv")
        df = pd.DataFrame([
            {"target_id": "T1", "label": "CP", "some_col": 123},
            {"target_id": "T2", "label": "FP", "some_col": 456},
        ])
        df.to_csv(path, index=False)

        cfg = DatasetTrainerConfig(data_path=path)
        with pytest.raises(IncompatibleDatasetError, match="lacks core transit features"):
            validate_and_load_dataset(cfg)


def test_dataset_trainer_group_split_prevents_leakage():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "dataset.csv")
        _create_mock_dataset(csv_path, n_records=80, n_targets=8)

        cfg = DatasetTrainerConfig(
            data_path=csv_path,
            label_col="disposition",
            test_size=0.25,
            random_state=42
        )
        model, summary = train_from_dataset(cfg)

        metrics = summary["metrics"]
        assert metrics["train_samples"] > 0
        assert metrics["test_samples"] > 0
        assert metrics["precision"] is not None
        assert metrics["recall"] is not None
        assert metrics["f1"] is not None
        assert summary["model_version"] is not None
        assert model.is_scientifically_trained is True
        assert model.is_synthetic is False
        assert model.feature_schema_version == FEATURE_SCHEMA_VERSION


def test_dataset_trainer_model_loading_and_inference():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "dataset.csv")
        model_path = os.path.join(tmpdir, "trained_model.joblib")
        _create_mock_dataset(csv_path, n_records=60, n_targets=6)

        cfg = DatasetTrainerConfig(
            data_path=csv_path,
            label_col="disposition",
            output_model_path=model_path,
            random_state=42
        )
        model, summary = train_from_dataset(cfg)

        assert os.path.exists(model_path)

        # Load with ExoplanetClassifier
        classifier = ExoplanetClassifier(model_path=model_path)
        assert classifier.is_synthetic is False

        # Run inference
        cand = DetectionCandidate(
            light_curve_id="00000000-0000-0000-0000-000000000001",
            target_id="TIC 999",
            mission=Mission.TESS,
            period_days=5.0,
            epoch_btjd=10.0,
            duration_hours=2.0,
            depth=0.015,
            bls_power=150.0,
            snr=25.0,
            transit_count=4,
            stellar_radius_solar=1.0,
            stellar_mass_solar=1.0,
            stellar_teff_k=5778.0
        )
        classified = classifier.predict(cand)
        assert 0.0 <= classified.planet_probability <= 1.0
        assert classified.metadata["is_synthetic_prediction"] is False
        assert classified.metadata["is_scientifically_trained"] is True
        assert classified.feature_schema_version == FEATURE_SCHEMA_VERSION
