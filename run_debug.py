import numpy as np
from app.detection.bls import BLSDetector
from app.contracts.models import LightCurve, Mission

def generate_synthetic_transit_light_curve():
    time = np.linspace(0, 20, 20 * 48)
    flux = np.ones_like(time)
    
    period = 5.0
    epoch = 2.0
    duration = 0.1
    depth = 0.02
    
    phase = (time - epoch + 0.5 * period) % period - 0.5 * period
    transit_mask = np.abs(phase) < (duration / 2.0)
    flux[transit_mask] -= depth
    
    noise = np.random.normal(0, 0.001, len(time))
    flux += noise
    
    return time.tolist(), flux.tolist(), (np.ones_like(time) * 0.001).tolist()

time, flux, err = generate_synthetic_transit_light_curve()
lc = LightCurve(target_id="123", mission=Mission.TESS, time=time, flux=flux, flux_error=err)

# Use preprocess_light_curve just to see if it messes up the transit
from app.preprocessing.pipeline import preprocess_light_curve
lc = preprocess_light_curve(lc)

detector = BLSDetector(min_period=3.0, max_period=8.0)
cands = detector.detect(lc)
for i, c in enumerate(cands):
    print(f"Cand {i}: period={c.period_days:.3f}, depth={c.depth:.4f}, snr={c.snr}, power={c.bls_power}")
