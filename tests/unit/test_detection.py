import pytest
import numpy as np
import time as time_lib
from uuid import uuid4
from app.contracts.models import LightCurve, Mission
from app.detection.bls import BLSDetector

def generate_transit_lc(length=1000, period=5.0, duration=0.1, depth=0.05, epoch=2.5, noise=0.001) -> LightCurve:
    time = np.linspace(0, 27, length)
    flux = np.ones(length)
    
    for i, t in enumerate(time):
        phase = (t - epoch) % period
        if phase > period - duration/2 or phase < duration/2:
            flux[i] = 1.0 - depth
            
    flux += np.random.normal(0, noise, length)
            
    return LightCurve(
        light_curve_id=uuid4(),
        target_id="TIC 123",
        mission=Mission.TESS,
        time=time.tolist(),
        flux=flux.tolist(),
        flux_error=(np.ones(length) * noise).tolist()
    )

def test_bls_detector_finds_injected_transit():
    lc = generate_transit_lc(length=1000, period=5.0, duration=0.1, depth=0.05, epoch=2.5)
    detector = BLSDetector(min_period=1.0, max_period=10.0, min_duration=0.05, max_duration=0.2)
    candidates = detector.detect(lc)
    
    assert len(candidates) == 1
    c = candidates[0]
    
    assert c.period_days == pytest.approx(5.0, abs=0.1)
    assert c.depth == pytest.approx(0.05, abs=0.01)
    assert c.duration_hours == pytest.approx(0.1 * 24, abs=1.0)
    assert c.snr is not None
    assert c.snr > 10.0
    assert c.transit_count >= 3

def test_flat_light_curve():
    time = np.linspace(0, 20, 100)
    flux = np.ones(100)
    lc = LightCurve(
        target_id="TIC 123",
        mission=Mission.TESS,
        time=time.tolist(),
        flux=flux.tolist()
    )
    detector = BLSDetector()
    assert detector.detect(lc) == []

def test_insufficient_data():
    time = np.linspace(0, 10, 5)
    flux = np.ones(5)
    lc = LightCurve(
        target_id="TIC 123",
        mission=Mission.TESS,
        time=time.tolist(),
        flux=flux.tolist()
    )
    detector = BLSDetector()
    assert detector.detect(lc) == []

def test_nans_handled():
    time = np.linspace(0, 20, 100)
    flux = np.ones(100)
    flux[10:90] = np.nan  # Break most of the curve
    lc = LightCurve(
        target_id="TIC 123",
        mission=Mission.TESS,
        time=time.tolist(),
        flux=flux.tolist()
    )
    # The valid mask should drop everything except 20 points
    detector = BLSDetector()
    candidates = detector.detect(lc)
    # Due to missing points, period span might be insufficient or it returns []
    assert len(candidates) == 0

def test_invalid_period_ranges():
    with pytest.raises(ValueError, match="min_period"):
        BLSDetector(min_period=10.0, max_period=5.0)

    with pytest.raises(ValueError, match="min_duration"):
        BLSDetector(min_duration=0.2, max_duration=0.1)

def test_bls_profile_realistic_sector_size():
    # TESS 2-min cadence for 27 days = roughly 20,000 points
    lc = generate_transit_lc(length=20000, period=8.2, duration=0.15, depth=0.02, epoch=3.1)
    
    detector = BLSDetector(min_period=1.0, max_period=15.0)
    
    start_time = time_lib.time()
    candidates = detector.detect(lc)
    end_time = time_lib.time()
    
    runtime = end_time - start_time
    assert len(candidates) == 1
    c = candidates[0]
    
    assert c.period_days == pytest.approx(8.2, abs=0.1)
    # Ensure it finishes reasonably fast (e.g. < 5 seconds) to prevent massive bottlenecks in the pipeline.
    # Note: runtime risk identified - a denser frequency grid would slow this down linearly.
    assert runtime < 5.0
