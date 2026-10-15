import math
import numpy as np
from app.contracts.models import DetectionCandidate

FEATURE_SCHEMA_VERSION = "2.0"

# Canonical feature list representing the exact 13 features used across training and inference
CANONICAL_FEATURES: list[str] = [
    "period_days",
    "duration_hours",
    "depth",
    "bls_power",
    "snr",
    "transit_count",
    "odd_even_depth_difference",
    "secondary_eclipse_depth",
    "stellar_radius_solar",
    "stellar_mass_solar",
    "stellar_teff_k",
    "depth_scaled",
    "semi_major_axis_au",
]

FEATURE_METADATA: dict[str, dict[str, str]] = {
    "period_days": {
        "units": "days",
        "definition": "Orbital period of the detected transit signal derived from Astropy BoxLeastSquares periodogram peak.",
        "missingness": "Required (strictly > 0).",
        "source": "BLS periodogram peak in app/detection/bls.py",
    },
    "duration_hours": {
        "units": "hours",
        "definition": "Transit duration from first to fourth contact derived from Astropy BLS best box duration.",
        "missingness": "Required (strictly > 0).",
        "source": "BLS duration grid in app/detection/bls.py",
    },
    "depth": {
        "units": "dimensionless (Delta F / F)",
        "definition": "Fractional transit depth from Astropy BLS box model.",
        "missingness": "Required (strictly >= 0).",
        "source": "BLS fitted depth in app/detection/bls.py",
    },
    "bls_power": {
        "units": "dimensionless",
        "definition": "Maximum periodogram power objective metric of the BLS detection.",
        "missingness": "Required (strictly >= 0).",
        "source": "BLS periodogram maximum in app/detection/bls.py",
    },
    "snr": {
        "units": "dimensionless",
        "definition": "Signal-to-noise ratio of the transit depth (depth / depth_err).",
        "missingness": "NaN if depth uncertainty <= 0 or missing.",
        "source": "Astropy BLS compute_stats()['depth'] ratio in app/detection/bls.py",
    },
    "transit_count": {
        "units": "dimensionless count",
        "definition": "Number of in-transit cadence windows observed within the light curve baseline.",
        "missingness": "Integer >= 0; 0 if no transits observed.",
        "source": "Astropy BLS compute_stats()['transit_times'] count in app/detection/bls.py",
    },
    "odd_even_depth_difference": {
        "units": "dimensionless (Delta F / F)",
        "definition": "Absolute difference between odd-transit and even-transit depths.",
        "missingness": "NaN if fewer than 2 transits observed or odd/even stats missing.",
        "source": "Astropy BLS compute_stats() depth_odd vs depth_even in app/detection/bls.py",
    },
    "secondary_eclipse_depth": {
        "units": "dimensionless (Delta F / F)",
        "definition": "Physical occultation depth at half-orbital phase (phase 0.5) from Astropy BLS depth_phased.",
        "missingness": "NaN if phased stats unavailable; non-detections clamped to 0.0.",
        "source": "Astropy BLS compute_stats()['depth_phased'][0] in app/detection/bls.py",
    },
    "stellar_radius_solar": {
        "units": "solar radii (R_sun)",
        "definition": "Host star radius from TESS Input Catalog (TIC) or authoritative archive.",
        "missingness": "NaN if unmeasured in catalog.",
        "source": "TIC Catalog lookup / MAST target metadata",
    },
    "stellar_mass_solar": {
        "units": "solar masses (M_sun)",
        "definition": "Host star mass from TESS Input Catalog (TIC) or authoritative archive.",
        "missingness": "NaN if unmeasured in catalog.",
        "source": "TIC Catalog lookup / MAST target metadata",
    },
    "stellar_teff_k": {
        "units": "Kelvin (K)",
        "definition": "Host star effective surface temperature from TIC or authoritative archive.",
        "missingness": "NaN if unmeasured in catalog.",
        "source": "TIC Catalog lookup / MAST target metadata",
    },
    "depth_scaled": {
        "units": "solar area units (R_sun^2)",
        "definition": "Scaled transit area proxy: depth * (stellar_radius_solar)^2 ~ (Rp / R_sun)^2.",
        "missingness": "NaN if stellar_radius_solar or depth is missing or non-positive.",
        "source": "Derived in app/features/engineering.py",
    },
    "semi_major_axis_au": {
        "units": "astronomical units (AU)",
        "definition": "Orbital semi-major axis proxy derived from Kepler's Third Law: (stellar_mass_solar * (period_days / 365.25)^2)^(1/3).",
        "missingness": "NaN if stellar_mass_solar or period_days is missing or non-positive.",
        "source": "Derived in app/features/engineering.py",
    },
}

def build_feature_vector(candidate: DetectionCandidate, include_legacy_alias: bool = True) -> dict[str, float]:
    """
    Transforms a DetectionCandidate into a flat feature dictionary for XGBoost/RandomForest.
    Missing data is explicitly represented as NaN to leverage tree-based models' native
    missing value handling. Fake astrophysical substitutes are avoided.
    """
    sec_depth = getattr(candidate, "secondary_eclipse_depth", None)
    if sec_depth is None:
        sec_depth = getattr(candidate, "secondary_eclipse_power", None)

    features = {
        "period_days": candidate.period_days,
        "duration_hours": candidate.duration_hours,
        "depth": candidate.depth,
        "bls_power": candidate.bls_power,
        "snr": candidate.snr if candidate.snr is not None else float('nan'),
        "transit_count": float(candidate.transit_count),
        "odd_even_depth_difference": candidate.odd_even_depth_difference if candidate.odd_even_depth_difference is not None else float('nan'),
        "secondary_eclipse_depth": sec_depth if sec_depth is not None else float('nan'),
    }

    # Backward compatibility for models/consumers expecting the legacy key
    if include_legacy_alias:
        features["secondary_eclipse_power"] = features["secondary_eclipse_depth"]

    # Stellar features (leave missing explicitly as NaN)
    stellar_r = candidate.stellar_radius_solar
    stellar_m = candidate.stellar_mass_solar
    teff = candidate.stellar_teff_k

    features["stellar_radius_solar"] = stellar_r if stellar_r is not None else float('nan')
    features["stellar_mass_solar"] = stellar_m if stellar_m is not None else float('nan')
    features["stellar_teff_k"] = teff if teff is not None else float('nan')

    # Derived stellar-normalized features
    # Transit depth = (Rp / Rs)^2  =>  Rp = Rs * sqrt(Depth)
    if stellar_r is not None and stellar_r > 0 and candidate.depth > 0:
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
