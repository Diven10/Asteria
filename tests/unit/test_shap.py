import pytest
import numpy as np
from uuid import uuid4

from app.contracts.models import DetectionCandidate, ClassifiedCandidate, Mission, PredictionLabel
from app.ml.train import TrainingPipeline
from app.explainability.shap_wrapper import ShapExplainer, ShapExplanation

def generate_synthetic_data(n_samples=20, n_targets=5):
    """
    Generates synthetic candidate data.
    """
    candidates = []
    labels = []
    for i in range(n_samples):
        target_id = f"TIC_{i % n_targets}"
        is_planet = (i % 2 == 0)
        
        cand = DetectionCandidate.model_construct(
            light_curve_id=uuid4(),
            target_id=target_id,
            mission=Mission.TESS,
            period_days=5.0,
            epoch_btjd=10.0,
            duration_hours=2.0,
            depth=0.01 if is_planet else 0.001,
            bls_power=100.0 if is_planet else 10.0,
            snr=15.0 if is_planet else 2.0,
            transit_count=5,
            stellar_radius_solar=1.0,
            stellar_mass_solar=1.0,
            stellar_teff_k=5778
        )
        candidates.append(cand)
        labels.append(1 if is_planet else 0)
    return candidates, labels

def test_shap_with_trained_model():
    candidates, labels = generate_synthetic_data()
    pipeline = TrainingPipeline(random_state=42)
    X, y, groups = pipeline.prepare_data(candidates, labels)
    pipeline.train_and_evaluate(X, y, groups, test_size=0.2)
    
    # 1. Initialize explainer
    explainer = ShapExplainer(pipeline.model)
    
    # 2. Mock a classified candidate
    cand = candidates[0]
    # We must use the same feature schema version as what we trained with
    from app.features.engineering import build_feature_vector, FEATURE_SCHEMA_VERSION
    features = build_feature_vector(cand)
    
    classified = ClassifiedCandidate.model_construct(
        candidate=cand,
        prediction=PredictionLabel.PLANET_CANDIDATE,
        planet_probability=0.8,
        model_name="ASTERIA-Test",
        model_version="1.0",
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        features=features
    )
    
    # 3. Explain
    explanation = explainer.explain(classified)
    
    assert isinstance(explanation, ShapExplanation)
    assert explanation.is_valid
    assert explanation.error_message is None
    
    # 4. Verify shape & schema
    # The number of SHAP values should equal the number of features
    assert len(explanation.feature_contributions) == len(features)
    assert set(explanation.feature_contributions.keys()) == set(features.keys())
    assert explanation.feature_schema_version == FEATURE_SCHEMA_VERSION
    
    # Base value and predicted value should be floats
    assert isinstance(explanation.base_value, float)
    assert isinstance(explanation.predicted_value, float)
    
    # 5. Global importance
    global_imp = explainer.get_global_importance(list(features.keys()))
    if getattr(pipeline.model, "__class__", None).__name__ == "RandomForestClassifier":
        assert global_imp.is_valid
        assert len(global_imp.importance) == len(features)
        
def test_shap_missing_model():
    explainer = ShapExplainer(None)
    
    # We must provide a mock candidate
    cand = DetectionCandidate.model_construct(
        light_curve_id=uuid4(), target_id="TIC", mission=Mission.TESS,
        period_days=5.0, epoch_btjd=10.0, duration_hours=2.0, depth=0.01,
        bls_power=10.0, transit_count=5
    )
    classified = ClassifiedCandidate.model_construct(
        candidate=cand, prediction=PredictionLabel.PLANET_CANDIDATE,
        planet_probability=0.8, model_name="mock", model_version="1.0",
        feature_schema_version="1.1", features={"a": 1.0}
    )
    explanation = explainer.explain(classified)
    assert not explanation.is_valid
    assert "trained model must be provided" in explanation.error_message

def test_shap_missing_features():
    from sklearn.ensemble import RandomForestClassifier
    model = RandomForestClassifier(n_estimators=1).fit([[0]], [0])
    explainer = ShapExplainer(model)
    
    cand = DetectionCandidate.model_construct(
        light_curve_id=uuid4(),
        target_id="TIC",
        mission=Mission.TESS,
        period_days=5.0,
        epoch_btjd=10.0,
        duration_hours=2.0,
        depth=0.01,
        bls_power=10.0,
        transit_count=5
    )
    classified = ClassifiedCandidate.model_construct(
        candidate=cand,
        prediction=PredictionLabel.PLANET_CANDIDATE,
        planet_probability=0.8,
        model_name="mock",
        model_version="1.0",
        feature_schema_version="1.1",
        features={}  # NO FEATURES
    )
    
    explanation = explainer.explain(classified)
    assert not explanation.is_valid
    assert "no features" in explanation.error_message

def test_shap_explainer_init_fails_cleanly():
    # Trying to initialize TreeExplainer with a string should fail gracefully
    explainer = ShapExplainer("invalid_model_type")
    
    cand = DetectionCandidate.model_construct(
        light_curve_id=uuid4(), target_id="TIC", mission=Mission.TESS,
        period_days=5.0, epoch_btjd=10.0, duration_hours=2.0, depth=0.01,
        bls_power=10.0, transit_count=5
    )
    classified = ClassifiedCandidate.model_construct(
        candidate=cand, prediction=PredictionLabel.PLANET_CANDIDATE,
        planet_probability=0.8, model_name="mock", model_version="1.0",
        feature_schema_version="1.1", features={"a": 1.0}
    )
    explanation = explainer.explain(classified)
    assert not explanation.is_valid
    assert "Failed to initialize TreeExplainer" in explanation.error_message
