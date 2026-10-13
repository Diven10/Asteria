import pytest
import math
import numpy as np
from uuid import uuid4

from app.contracts.models import DetectionCandidate, Mission
from app.features.engineering import build_feature_vector, FEATURE_SCHEMA_VERSION

def _mock_candidate(
    period_days=5.0, depth=0.01, stellar_r=1.0, stellar_m=1.0, teff=5778
) -> DetectionCandidate:
    return DetectionCandidate(
        light_curve_id=uuid4(),
        target_id="TIC 123",
        mission=Mission.TESS,
        period_days=period_days,
        epoch_btjd=10.0,
        duration_hours=2.0,
        depth=depth,
        bls_power=50.0,
        snr=10.0,
        transit_count=4,
        odd_even_depth_difference=0.001,
        secondary_eclipse_power=2.0,
        stellar_radius_solar=stellar_r,
        stellar_mass_solar=stellar_m,
        stellar_teff_k=teff
    )

def test_build_feature_vector_schema_version():
    assert FEATURE_SCHEMA_VERSION == "1.1"

def test_feature_vector_with_complete_data():
    cand = _mock_candidate(period_days=365.25, depth=0.01, stellar_r=2.0, stellar_m=1.0)
    features = build_feature_vector(cand)
    
    # Base features
    assert features["period_days"] == 365.25
    assert features["depth"] == 0.01
    assert features["snr"] == 10.0
    assert features["transit_count"] == 4.0
    
    # Stellar features
    assert features["stellar_radius_solar"] == 2.0
    assert features["stellar_mass_solar"] == 1.0
    assert features["stellar_teff_k"] == 5778
    
    # Derived normalized features
    # depth_scaled = depth * R^2 = 0.01 * 4 = 0.04
    assert np.isclose(features["depth_scaled"], 0.04)
    
    # semi_major_axis_au = (M * (P_years)^2)^(1/3) = (1.0 * (1.0)^2)^(1/3) = 1.0
    assert np.isclose(features["semi_major_axis_au"], 1.0)

def test_feature_vector_with_missing_stellar_data():
    cand = _mock_candidate(stellar_r=None, stellar_m=None, teff=None)
    # Also test missing optional detection fields
    cand.snr = None
    cand.odd_even_depth_difference = None
    cand.secondary_eclipse_power = None
    
    features = build_feature_vector(cand)
    
    # The missing values should be explicitly NaNs, not fake 0s or -1s
    assert np.isnan(features["stellar_radius_solar"])
    assert np.isnan(features["stellar_mass_solar"])
    assert np.isnan(features["stellar_teff_k"])
    assert np.isnan(features["snr"])
    assert np.isnan(features["odd_even_depth_difference"])
    assert np.isnan(features["secondary_eclipse_power"])
    
    # Derived features that depend on stellar properties should also be NaNs
    assert np.isnan(features["depth_scaled"])
    assert np.isnan(features["semi_major_axis_au"])
    
    # Base features should still be extracted successfully
    assert features["period_days"] == 5.0
    assert features["depth"] == 0.01
    assert features["transit_count"] == 4.0
