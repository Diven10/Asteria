import pytest
from uuid import uuid4
from app.contracts.models import DetectionCandidate, ClassifiedCandidate, Mission, PredictionLabel
from app.validation.rules import ValidationResult, RuleResult
from app.planet_properties.estimator import PlanetProperties
from app.ranking.ops import calculate_ops, rank_candidates, OPSConfig

def build_mock_candidate(snr, teff):
    cand = DetectionCandidate.model_construct(
        candidate_id=uuid4(),
        light_curve_id=uuid4(),
        target_id="TIC",
        mission=Mission.TESS,
        period_days=5.0,
        epoch_btjd=10.0,
        duration_hours=2.0,
        depth=0.01,
        bls_power=100.0,
        snr=snr,
        stellar_teff_k=teff
    )
    return ClassifiedCandidate.model_construct(
        candidate=cand,
        prediction=PredictionLabel.PLANET_CANDIDATE,
        planet_probability=0.9,
        model_name="mock",
        model_version="1.0",
        feature_schema_version="1.0"
    )

def test_high_quality_candidate():
    classified = build_mock_candidate(snr=25.0, teff=3500)
    # Earth-sized planet around M-dwarf with high SNR and prob
    props = PlanetProperties(radius_earth=1.0, size_class="Earth-size", habitable_zone_proxy=True)
    validation = ValidationResult(is_valid_astrophysically=True, fused_probability=0.9, rules=[])
    
    ops = calculate_ops(classified, props, validation)
    
    # Check breakdown
    assert ops.breakdown.confidence_score == 36.0 # 0.9 * 40
    assert ops.breakdown.snr_score == 20.0 # Capped at 20
    assert ops.breakdown.radius_score == 20.0 # Ideal radius
    assert ops.breakdown.host_star_score == 20.0 # M-dwarf
    assert ops.breakdown.fp_penalty_applied is False
    
    assert ops.total_score == 96.0

def test_low_quality_candidate():
    # Low prob, low SNR, bad size, hot star
    classified = build_mock_candidate(snr=5.0, teff=7000)
    classified.planet_probability = 0.2
    
    props = PlanetProperties(radius_earth=10.0, size_class="Giant", habitable_zone_proxy=False)
    validation = ValidationResult(is_valid_astrophysically=True, fused_probability=0.2, rules=[])
    
    ops = calculate_ops(classified, props, validation)
    
    assert ops.breakdown.confidence_score == 8.0 # 0.2 * 40
    assert ops.breakdown.snr_score == 5.0 # (5/20) * 20
    assert ops.breakdown.radius_score == 0.0 # > 6.0
    assert ops.breakdown.host_star_score == 0.0 # > 6000
    assert ops.breakdown.fp_penalty_applied is False
    
    assert ops.total_score == 13.0

def test_false_positive_candidate():
    classified = build_mock_candidate(snr=20.0, teff=3500)
    props = PlanetProperties(radius_earth=1.0, size_class="Earth-size", habitable_zone_proxy=True)
    # Fails astrophysical checks
    validation = ValidationResult(is_valid_astrophysically=False, fused_probability=0.9, rules=[])
    
    ops = calculate_ops(classified, props, validation)
    
    # Base score is 96.0, but FP penalty 0.5 applies
    assert ops.breakdown.fp_penalty_applied is True
    assert ops.total_score == 48.0

def test_missing_data_graceful_handling():
    classified = build_mock_candidate(snr=None, teff=None)
    props = PlanetProperties(radius_earth=None, size_class="Unknown", habitable_zone_proxy=False)
    validation = ValidationResult(is_valid_astrophysically=True, fused_probability=0.9, rules=[])
    
    ops = calculate_ops(classified, props, validation)
    
    assert ops.breakdown.snr_score == 0.0
    assert ops.breakdown.radius_score == 0.0
    assert ops.breakdown.host_star_score == 0.0
    assert ops.total_score == 36.0 # Only confidence score

def test_ranking_ties():
    cand1 = build_mock_candidate(snr=20.0, teff=3500)
    cand1.candidate.target_id = "B"
    cand1.candidate.period_days = 2.0
    
    cand2 = build_mock_candidate(snr=20.0, teff=3500)
    cand2.candidate.target_id = "A"
    cand2.candidate.period_days = 2.0
    
    cand3 = build_mock_candidate(snr=20.0, teff=3500)
    cand3.candidate.target_id = "C"
    cand3.candidate.period_days = 1.0 # Shorter period wins tie if score is same
    
    props = PlanetProperties(radius_earth=1.0, size_class="Earth-size", habitable_zone_proxy=True)
    validation = ValidationResult(is_valid_astrophysically=True, fused_probability=0.9, rules=[])
    
    ops1 = calculate_ops(cand1, props, validation)
    ops2 = calculate_ops(cand2, props, validation)
    ops3 = calculate_ops(cand3, props, validation)
    
    # All have same score (96.0)
    ranked = rank_candidates([ops1, ops2, ops3])
    
    # Order should be: cand3 (shorter period), then cand2 (target_id A), then cand1 (target_id B)
    assert ranked[0].target_id == "C"
    assert ranked[1].target_id == "A"
    assert ranked[2].target_id == "B"
