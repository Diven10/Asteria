import pytest
from uuid import uuid4
from app.contracts.models import DetectionCandidate, ClassifiedCandidate, Mission, PredictionLabel
from app.validation.rules import validate_candidate, ValidationConfig

def _mock_classified(
    depth=0.01,
    snr=15.0,
    odd_even_diff=0.0001,
    secondary_power=0.5,
    bls_power=50.0,
    stellar_r=1.0,
    prob=0.9
):
    cand = DetectionCandidate.model_construct(
        light_curve_id=uuid4(),
        target_id="TIC 123",
        mission=Mission.TESS,
        period_days=5.0,
        epoch_btjd=10.0,
        duration_hours=2.0,
        depth=depth,
        bls_power=bls_power,
        snr=snr,
        transit_count=4,
        odd_even_depth_difference=odd_even_diff,
        secondary_eclipse_power=secondary_power,
        stellar_radius_solar=stellar_r,
        stellar_mass_solar=1.0,
        stellar_teff_k=5778
    )
    return ClassifiedCandidate.model_construct(
        candidate=cand,
        prediction=PredictionLabel.PLANET_CANDIDATE,
        planet_probability=prob,
        model_name="test",
        model_version="1.0",
        feature_schema_version="1.1",
        features={}
    )

def test_validation_obvious_transit():
    # Excellent candidate
    classified = _mock_classified(depth=0.01, odd_even_diff=0.0001, snr=20.0, secondary_power=0.0, stellar_r=1.0)
    result = validate_candidate(classified)
    
    assert result.is_valid_astrophysically
    assert result.fused_probability == 0.9
    
    # 5 checks are returned
    assert len(result.rules) == 5
    assert all(r.passed for r in result.rules)

def test_validation_odd_even_mismatch():
    # Odd even depth diff is huge (eclipsing binary)
    classified = _mock_classified(depth=0.01, odd_even_diff=0.005) # 50% of depth
    result = validate_candidate(classified)
    
    assert not result.is_valid_astrophysically
    # Probability should be severely penalized (0.9 * 0.1) = 0.09
    assert pytest.approx(result.fused_probability, abs=0.01) == 0.09
    
    failed = [r for r in result.rules if not r.passed]
    assert len(failed) == 1
    assert failed[0].rule_name == "odd_even"
    assert "Difference ratio 0.500" in failed[0].reason

def test_validation_secondary_eclipse():
    classified = _mock_classified(bls_power=50.0, secondary_power=25.0)
    result = validate_candidate(classified)
    
    assert not result.is_valid_astrophysically
    
    failed = [r for r in result.rules if not r.passed]
    assert len(failed) == 1
    assert failed[0].rule_name == "secondary_eclipse"

def test_validation_low_snr():
    classified = _mock_classified(snr=5.0)
    result = validate_candidate(classified)
    
    assert not result.is_valid_astrophysically
    failed = [r for r in result.rules if not r.passed]
    assert len(failed) == 1
    assert failed[0].rule_name == "snr"

def test_validation_v_shaped_deep_transit():
    # Depth is 0.06 (6%), which is above the 5% threshold
    classified = _mock_classified(depth=0.06, stellar_r=1.0)
    result = validate_candidate(classified)
    
    assert not result.is_valid_astrophysically
    failed = [r for r in result.rules if not r.passed]
    # In this case, depth > 5% will fail the depth_v_shape rule, 
    # but ALSO, 0.06 with R_sun=1.0 gives R_planet = 109.1 * sqrt(0.06) = 26.7 R_earth
    # which fails the max_radius_earth check (22.0)
    assert len(failed) == 2
    rule_names = {r.rule_name for r in failed}
    assert "depth_v_shape" in rule_names
    assert "planet_radius" in rule_names

def test_validation_missing_catalog_info():
    classified = _mock_classified(stellar_r=None, snr=None)
    classified.candidate.odd_even_depth_difference = None
    classified.candidate.secondary_eclipse_power = None
    
    result = validate_candidate(classified)
    
    # Missing information should not automatically fail the candidate, 
    # but it flags it as is_missing_data=True
    assert result.is_valid_astrophysically
    
    missing_rules = [r for r in result.rules if r.is_missing_data]
    # SNR, odd_even, secondary_eclipse, planet_radius
    assert len(missing_rules) == 4
    
    assert result.fused_probability == 0.9 # No penalty
