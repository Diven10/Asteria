import pytest
import math
from uuid import uuid4
from app.contracts.models import DetectionCandidate, Mission
from app.planet_properties.estimator import estimate_properties, PlanetProperties

def _mock_candidate(
    period_days=365.25, 
    depth=0.0, 
    stellar_r=1.0, 
    stellar_m=1.0, 
    teff=5778
) -> DetectionCandidate:
    # depth = (1 / 109.1)^2 approx 8.4e-5 for an Earth-like planet around Sun
    return DetectionCandidate(
        light_curve_id=uuid4(),
        target_id="TIC 123",
        mission=Mission.TESS,
        period_days=period_days,
        epoch_btjd=10.0,
        duration_hours=10.0,
        depth=depth,
        bls_power=50.0,
        snr=10.0,
        transit_count=4,
        stellar_radius_solar=stellar_r,
        stellar_mass_solar=stellar_m,
        stellar_teff_k=teff
    )

def test_estimate_properties_earth_analogue():
    # Earth transit depth across the Sun is approx 84 ppm = 0.000084
    earth_depth = (1.0 / 109.1) ** 2
    cand = _mock_candidate(
        period_days=365.25,
        depth=earth_depth,
        stellar_r=1.0,
        stellar_m=1.0,
        teff=5778
    )
    
    props = estimate_properties(cand)
    
    # 1. Radius ~ 1 Earth radius
    assert props.radius_earth == pytest.approx(1.0, abs=0.01)
    assert props.size_class == "Earth-size"
    
    # 2. Semi-major axis ~ 1 AU
    assert props.semi_major_axis_au == pytest.approx(1.0, abs=0.01)
    
    # 3. Insolation flux ~ 1 S_earth
    assert props.insolation_flux_earth == pytest.approx(1.0, abs=0.01)
    
    # 4. Equilibrium temp ~ 255K for Earth
    assert props.equilibrium_temperature_k == pytest.approx(255.0, abs=1.0)
    
    # 5. Habitable zone proxy
    assert props.habitable_zone_proxy is True

def test_estimate_properties_missing_stellar_parameters():
    cand = _mock_candidate(stellar_r=None, stellar_m=None, teff=None)
    props = estimate_properties(cand)
    
    assert props.radius_earth is None
    assert props.semi_major_axis_au is None
    assert props.equilibrium_temperature_k is None
    assert props.insolation_flux_earth is None
    assert props.size_class == "Unknown"
    assert props.habitable_zone_proxy is False

def test_estimate_properties_invalid_parameters():
    # Negative depth (unphysical transit)
    # Use model_construct to bypass Pydantic validation and test our estimator logic directly
    cand = DetectionCandidate.model_construct(depth=-0.01, stellar_radius_solar=1.0)
    props = estimate_properties(cand)
    
    # Radius shouldn't be calculated if depth < 0
    assert props.radius_earth is None

def test_estimate_properties_boundary_classes():
    # Jupiter analogue (R_earth ~ 11.2)
    # depth = (11.2 / 109.1)^2 = 0.0105
    cand = _mock_candidate(depth=0.0105, stellar_r=1.0)
    props = estimate_properties(cand)
    assert props.size_class == "Gas Giant"
    
    # Sub-Neptune (R_earth ~ 3.0)
    cand = _mock_candidate(depth=(3.0 / 109.1)**2, stellar_r=1.0)
    props = estimate_properties(cand)
    assert props.size_class == "Sub-Neptune"
    
    # Super-Earth (R_earth ~ 1.5)
    cand = _mock_candidate(depth=(1.5 / 109.1)**2, stellar_r=1.0)
    props = estimate_properties(cand)
    assert props.size_class == "Super-Earth"

    # Sub-Earth (R_earth ~ 0.5)
    cand = _mock_candidate(depth=(0.5 / 109.1)**2, stellar_r=1.0)
    props = estimate_properties(cand)
    assert props.size_class == "Sub-Earth"
