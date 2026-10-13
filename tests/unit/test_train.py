import pytest
import os
import numpy as np
import tempfile
from uuid import uuid4

from app.contracts.models import DetectionCandidate, Mission, PredictionLabel
from app.ml.train import TrainingPipeline
from app.ml.classifier import ExoplanetClassifier
from app.features.engineering import FEATURE_SCHEMA_VERSION

def generate_synthetic_data(n_samples=100, n_targets=20):
    """
    Generates synthetic candidate data grouped by multiple targets (host stars).
    Ensures that some targets have multiple candidates (light curve segments).
    Label 1 = planet, 0 = false positive.
    """
    candidates = []
    labels = []
    
    # We assign targets 0 to n_targets-1
    for i in range(n_samples):
        target_id = f"TIC_{i % n_targets}"
        is_planet = (i % 2 == 0) # Alternate labels
        
        # Make the planet features distinct enough so the model can learn something
        depth = 0.01 if is_planet else 0.0001
        snr = 15.0 if is_planet else 2.0
        bls_power = 100.0 if is_planet else 10.0
        
        # Add some jitter to avoid perfectly identical values which break HistGradientBoosting binning
        import random
        period_days = 5.0 + random.uniform(-0.1, 0.1)
        depth = depth + random.uniform(0, 0.0001)
        snr = snr + random.uniform(-0.5, 0.5)
        
        cand = DetectionCandidate(
            light_curve_id=uuid4(),
            target_id=target_id,
            mission=Mission.TESS,
            period_days=period_days,
            epoch_btjd=10.0,
            duration_hours=2.0 + random.uniform(-0.1, 0.1),
            depth=depth,
            bls_power=bls_power,
            snr=snr,
            transit_count=5,
            stellar_radius_solar=1.0,
            stellar_mass_solar=1.0,
            stellar_teff_k=5778
        )
        candidates.append(cand)
        labels.append(1 if is_planet else 0)
        
    return candidates, labels

def test_group_aware_split_prevents_leakage():
    candidates, labels = generate_synthetic_data(n_samples=200, n_targets=10)
    
    pipeline = TrainingPipeline()
    X, y, groups = pipeline.prepare_data(candidates, labels)
    
    from sklearn.model_selection import GroupShuffleSplit
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(X, y, groups=groups))
    
    train_groups = set(groups[train_idx])
    test_groups = set(groups[test_idx])
    
    # CRITICAL constraint: No target_id in train should appear in test
    intersection = train_groups.intersection(test_groups)
    assert len(intersection) == 0, f"Leakage detected! Shared targets: {intersection}"

def test_training_pipeline_and_metrics():
    candidates, labels = generate_synthetic_data(n_samples=100, n_targets=10)
    
    pipeline = TrainingPipeline(random_state=42)
    X, y, groups = pipeline.prepare_data(candidates, labels)
    
    metrics = pipeline.train_and_evaluate(X, y, groups, test_size=0.2)
    
    assert metrics["pr_auc"] is None
    assert metrics["precision"] is None
    assert metrics["recall"] is None
    assert metrics["confusion_matrix"] is None
    assert metrics["is_scientifically_trained"] is False # explicitly marked untrained
    
    # We do not assert metric bounds since they are omitted to avoid fabrication

def test_model_persistence_and_inference_wrapper():
    candidates, labels = generate_synthetic_data(n_samples=50, n_targets=5)
    
    pipeline = TrainingPipeline(random_state=42)
    X, y, groups = pipeline.prepare_data(candidates, labels)
    pipeline.train_and_evaluate(X, y, groups, test_size=0.2)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = os.path.join(tmpdir, "xgboost_model.pkl")
        pipeline.save_model(model_path)
        
        assert os.path.exists(model_path)
        
        # Load using our actual inference wrapper
        classifier = ExoplanetClassifier(model_path=model_path)
        assert classifier.is_synthetic is False
        
        # Test inference
        cand = candidates[0]
        classified = classifier.predict(cand)
        
        # Validate probability bounds
        assert 0.0 <= classified.planet_probability <= 1.0
        
        # Validate schema version passes through
        assert classified.feature_schema_version == FEATURE_SCHEMA_VERSION
        
        # Validate metadata
        assert classified.model_name == "ASTERIA-Untrained-Estimator"
        assert classified.metadata.get("is_synthetic_prediction") is False
