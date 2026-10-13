import math
import numpy as np
from app.contracts.models import DetectionCandidate

FEATURE_SCHEMA_VERSION = "1.1"

def build_feature_vector(candidate: DetectionCandidate) -> dict[str, float]:
    """
    Transforms a DetectionCandidate into a flat feature dictionary for XGBoost.
    Missing data is explicitly represented as NaN to leverage XGBoost's 
    native missing value handling. Fake astrophysical substitutes are avoided.
    """
    features = {
        "period_days": candidate.period_days,
        "duration_hours": candidate.duration_hours,
        "depth": candidate.depth,
        "bls_power": candidate.bls_power,
        "snr": candidate.snr if candidate.snr is not None else float('nan'),
        "transit_count": float(candidate.transit_count),
        "odd_even_depth_difference": candidate.odd_even_depth_difference if candidate.odd_even_depth_difference is not None else float('nan'),
        "secondary_eclipse_power": candidate.secondary_eclipse_power if candidate.secondary_eclipse_power is not None else float('nan'),
    }
    
    # Stellar features (leave missing explicitly as NaN)
    stellar_r = candidate.stellar_radius_solar
    stellar_m = candidate.stellar_mass_solar
    teff = candidate.stellar_teff_k
    
    features["stellar_radius_solar"] = stellar_r if stellar_r is not None else float('nan')
    features["stellar_mass_solar"] = stellar_m if stellar_m is not None else float('nan')
    features["stellar_teff_k"] = teff if teff is not None else float('nan')
    
    # Derived stellar-normalized features
    # If the star is huge, a 1% depth means a much bigger planet than if the star is small.
    # Transit depth = (Rp / Rs)^2  =>  Rp = Rs * sqrt(Depth)
    # So a normalized depth proxy that correlates strongly with absolute planet size:
    if stellar_r is not None and stellar_r > 0 and candidate.depth > 0:
        # Scale to a relative metric: depth scaled by the squared stellar radius.
        # This gives a proxy for the actual squared physical radius of the planet relative to the sun.
        features["depth_scaled"] = candidate.depth * (stellar_r ** 2)
    else:
        features["depth_scaled"] = float('nan')
        
    # Orbit semi-major axis proxy (Kepler's third law)
    if stellar_m is not None and stellar_m > 0 and candidate.period_days > 0:
        period_years = candidate.period_days / 365.25
        a_au = (stellar_m * (period_years ** 2)) ** (1/3)
        features["semi_major_axis_au"] = a_au
    else:
        features["semi_major_axis_au"] = float('nan')

    return features
