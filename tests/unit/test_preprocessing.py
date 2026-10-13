import pytest
import numpy as np
from uuid import uuid4
from app.contracts.models import LightCurve, Mission, Cadence
from app.preprocessing.pipeline import preprocess_light_curve, PreprocessingConfig

def generate_synthetic_transit(
    length=500, baseline=1000.0, depth=0.01, noise_level=0.001, trend_slope=0.0
):
    """Generates a synthetic transit with noise and optional linear trend."""
    time = np.linspace(0, 20, length)
    flux = np.ones(length) * baseline
    
    # Add a linear trend
    flux += trend_slope * time
    
    # Inject a transit in the middle
    transit_start = length // 2 - 10
    transit_end = length // 2 + 10
    flux[transit_start:transit_end] -= baseline * depth
    
    # Add white noise
    flux += np.random.normal(0, baseline * noise_level, length)
    
    return time, flux, transit_start, transit_end

def test_preprocess_handles_nans_and_outliers():
    time = np.linspace(0, 10, 100)
    flux = np.ones(100) * 1000.0
    flux[10] = np.nan
    flux[20] = 50000.0  # Massive outlier
    
    lc = LightCurve(
        light_curve_id=uuid4(),
        target_id="TIC 123",
        mission=Mission.TESS,
        cadence=Cadence.SHORT,
        time=time.tolist(),
        flux=flux.tolist()
    )
    
    processed = preprocess_light_curve(lc)
    
    # 1. NaNs handled
    # 2. Outliers handled
    # 6. Output remains finite and aligned
    assert len(processed.time) == 98
    assert len(processed.flux) == 98
    assert not np.isnan(processed.flux).any()
    assert max(processed.flux) < 2.0  # Outlier removed, and normalized
    assert processed.metadata.get("preprocessing") == "adaptive"

def test_preprocess_preserves_transit_depth_and_detrends():
    time, flux, t_start, t_end = generate_synthetic_transit(
        length=500, baseline=1000.0, depth=0.05, noise_level=0.0001, trend_slope=5.0
    )
    
    lc = LightCurve(
        target_id="TIC 123",
        mission=Mission.TESS,
        time=time.tolist(),
        flux=flux.tolist()
    )
    
    # 3. Normalization works
    # 4. Detrending works
    # 5. Transit depth not catastrophically altered
    
    config = PreprocessingConfig(detrend_window_length=101)
    processed = preprocess_light_curve(lc, config=config)
    
    # The baseline should be normalized to ~1.0
    baseline_flux = np.median(processed.flux)
    assert np.isclose(baseline_flux, 1.0, atol=0.01)
    
    # The transit depth should still be ~0.05
    # The transit should still be roughly in the middle
    transit_flux = np.min(processed.flux)
    measured_depth = baseline_flux - transit_flux
    
    # Because of flattening and noise, we allow some tolerance, but it shouldn't be destroyed
    assert 0.04 < measured_depth < 0.06
    
    # The linear trend (which was 5.0 * 20 = +100 units across the curve) should be gone
    # First and last points should be near 1.0
    assert np.isclose(processed.flux[0], 1.0, atol=0.02)
    assert np.isclose(processed.flux[-1], 1.0, atol=0.02)
    
def test_insufficient_data_handled():
    with pytest.raises(ValueError, match="at least two samples"):
        LightCurve(
            target_id="TIC 123",
            mission=Mission.TESS,
            time=[1.0],
            flux=[1000.0]
        )
        
    # Let's bypass pydantic validation for the test to ensure our code is safe too
    # Actually, we can't easily bypass pydantic. Let's just create one with 2 elements.
    lc2 = LightCurve(
        target_id="TIC 123",
        mission=Mission.TESS,
        time=[1.0, 2.0],
        flux=[1000.0, 1000.0]
    )
    
    processed = preprocess_light_curve(lc2)
    assert len(processed.flux) == 2
