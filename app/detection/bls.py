import numpy as np
from astropy.timeseries import BoxLeastSquares
from app.contracts.models import LightCurve, DetectionCandidate
from app.detection.interfaces import TransitDetector

class BLSDetector(TransitDetector):
    """Box Least Squares implementation for transit detection."""
    
    def __init__(self, min_period=0.5, max_period=20.0, min_duration=0.01, max_duration=0.2):
        if min_period >= max_period:
            raise ValueError(f"Invalid period range: min_period ({min_period}) must be less than max_period ({max_period})")
        if min_duration >= max_duration:
            raise ValueError("Invalid duration range: min_duration must be less than max_duration")
            
        self.min_period = min_period
        self.max_period = max_period
        self.min_duration = min_duration
        self.max_duration = max_duration

    def detect(self, lc: LightCurve) -> list[DetectionCandidate]:
        if len(lc.time) < 10:
            return []

        t = np.array(lc.time)
        y = np.array(lc.flux)
        
        # Check for NaNs
        valid_mask = np.isfinite(t) & np.isfinite(y)
        if lc.flux_error is not None:
            dy = np.array(lc.flux_error)
            valid_mask &= np.isfinite(dy)
            dy = dy[valid_mask]
        else:
            dy = None
            
        t = t[valid_mask]
        y = y[valid_mask]
        
        # If after NaN removal we don't have enough data
        if len(t) < 10:
            return []
            
        # Check if light curve is completely flat
        if np.ptp(y) == 0:
            return []
            
        # Ensure time span is at least min_period, otherwise we can't find a full period
        t_span = t[-1] - t[0]
        if t_span < self.min_period:
            return []

        model = BoxLeastSquares(t, y, dy=dy)
        
        # Limit max period to time span
        actual_max_period = min(self.max_period, t_span)
        if self.min_period >= actual_max_period:
            # Not enough baseline to search this period range
            return []
            
        # Configurable grid spacing
        # For a realistic sector-sized fixture (~27 days, 2 min cadence -> ~20k points), 
        # a 1000-point period grid can be computationally expensive. We cap it to maintain reasonable runtime.
        periods = np.linspace(self.min_period, actual_max_period, 1000)
        durations = np.linspace(self.min_duration, self.max_duration, 10)

        results = model.power(periods, durations)

        best_idx = np.argmax(results.power)
        best_period = results.period[best_idx]
        best_duration = results.duration[best_idx]
        best_epoch = results.transit_time[best_idx]
        best_power = results.power[best_idx]
        best_depth = results.depth[best_idx]
        
        # If the detected power is virtually 0 (e.g. noise only)
        if best_power <= 0:
            return []

        stats = model.compute_stats(best_period, best_duration, best_epoch)
        depth_val = stats.get('depth', [0, 0])
        if isinstance(depth_val, (tuple, list)):
            snr = depth_val[0] / depth_val[1] if len(depth_val) > 1 and depth_val[1] > 0 else 0
        else:
            snr = best_depth / stats.get('depth_err', 1e-6) if stats.get('depth_err', 0) > 0 else 0

        transit_times = stats.get('transit_times', [])
        transit_count = len(transit_times)
        
        depth_odd = stats.get('depth_odd', [0, 0])
        depth_even = stats.get('depth_even', [0, 0])
        
        odd_depth = depth_odd[0] if isinstance(depth_odd, (tuple, list)) else depth_odd
        even_depth = depth_even[0] if isinstance(depth_even, (tuple, list)) else depth_even
        odd_even_diff = abs(odd_depth - even_depth) if (odd_depth and even_depth) else None
        
        # In Astropy BoxLeastSquares.compute_stats:
        # - depth_phased: (depth, depth_err) evaluated at the fiducial period with phase offset by 0.5.
        #   This is the true physical secondary eclipse measurement (occultation at half-orbital phase).
        # - depth_half: (depth, depth_err) evaluated for a model with half the fiducial period (P/2).
        #   This is the half-period harmonic, NOT a secondary eclipse.
        phased_stat = stats.get('depth_phased', (0.0, 0.0))
        sec_depth_raw = phased_stat[0] if isinstance(phased_stat, (tuple, list)) and len(phased_stat) >= 1 else phased_stat
        if sec_depth_raw is not None and np.isfinite(sec_depth_raw):
            # Sign convention: depth_phased is y_out - y_in at phase 0.5.
            # Positive value indicates a flux dip (secondary eclipse). Clamped to >= 0 for physical depth.
            sec_depth_val = max(0.0, float(sec_depth_raw))
        else:
            sec_depth_val = None

        half_stat = stats.get('depth_half', (0.0, 0.0))
        half_depth_raw = half_stat[0] if isinstance(half_stat, (tuple, list)) and len(half_stat) >= 1 else half_stat
        if half_depth_raw is not None and np.isfinite(half_depth_raw):
            half_depth_val = max(0.0, float(half_depth_raw))
        else:
            half_depth_val = None

        candidate = DetectionCandidate(
            light_curve_id=lc.light_curve_id,
            target_id=lc.target_id,
            mission=lc.mission,
            period_days=float(best_period),
            epoch_btjd=float(best_epoch),
            duration_hours=float(best_duration * 24),
            depth=float(best_depth),
            bls_power=float(best_power),
            snr=float(snr) if snr > 0 else None,
            transit_count=transit_count,
            odd_even_depth_difference=float(odd_even_diff) if odd_even_diff is not None else None,
            secondary_eclipse_depth=sec_depth_val,
            secondary_eclipse_power=sec_depth_val,
            half_period_depth=half_depth_val,
        )


        return [candidate]
