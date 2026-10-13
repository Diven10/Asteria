import numpy as np
import lightkurve as lk
from dataclasses import dataclass
from typing import Any

from app.contracts.models import LightCurve

@dataclass(frozen=True)
class PreprocessingConfig:
    """Explicit configuration for adaptive preprocessing."""
    sigma_clip: float = 5.0
    detrend_window_length: int = 101
    interpolate_gaps: bool = False
    normalize: bool = True
    remove_nans: bool = True

def preprocess_light_curve(
    lc_contract: LightCurve, 
    config: PreprocessingConfig | None = None
) -> LightCurve:
    """Applies adaptive preprocessing to a LightCurve contract.
    
    Steps:
    1. Remove NaNs
    2. Normalize flux
    3. Remove outliers (sigma clip)
    4. Detrend / adaptive noise filtering (flatten)
    5. Interpolate gaps
    """
    
    if config is None:
        config = PreprocessingConfig()
        
    time_array = np.array(lc_contract.time)
    flux_array = np.array(lc_contract.flux)
    flux_err_array = np.array(lc_contract.flux_error) if lc_contract.flux_error is not None else None
    
    # Handle insufficient data gracefully
    if len(time_array) < 2:
        return lc_contract # Cannot preprocess fewer than 2 points
        
    lk_lc = lk.LightCurve(time=time_array, flux=flux_array, flux_err=flux_err_array)
    
    # 1. NaN removal
    if config.remove_nans:
        lk_lc = lk_lc.remove_nans()
        if len(lk_lc) < 2:
            # If everything was NaNs, gracefully return what's left or empty (well, return as is safely)
            pass
            
    # 2. Flux normalization
    if config.normalize and len(lk_lc) > 0:
        # Check if already normalized/zero-centered to avoid warnings or catastrophic division
        median_flux = np.nanmedian(lk_lc.flux.value)
        if median_flux > 0.1: # simple heuristic to avoid normalizing zero-centered flux
            lk_lc = lk_lc.normalize()
        
    # 3. Outlier clipping
    if config.sigma_clip > 0 and len(lk_lc) > 0:
        lk_lc = lk_lc.remove_outliers(sigma=config.sigma_clip)
        
    # 4. Detrending (adaptive noise filtering)
    # Using lightkurve's flatten which applies a median filter (Savitzky-Golay)
    # This detrends without destroying transit-shaped signals (provided window > transit duration).
    if config.detrend_window_length > 0 and len(lk_lc) > config.detrend_window_length:
        # Window length must be odd
        window = config.detrend_window_length
        if window % 2 == 0:
            window += 1
        lk_lc = lk_lc.flatten(window_length=window)
        
    # 5. Gap handling / interpolation
    if config.interpolate_gaps and hasattr(lk_lc, 'fill_gaps') and len(lk_lc) > 0:
        # fill_gaps relies on pandas/numpy interpolation
        lk_lc = lk_lc.fill_gaps()
        
    # Safe extraction of flux_error handling potential NaNs generated
    flux_err_list = None
    if lk_lc.flux_err is not None:
        fe_vals = lk_lc.flux_err.value
        if not np.all(np.isnan(fe_vals)):
            # Pydantic requires finite floats. Replace NaNs in flux_err with 0 or drop them? 
            # We must output finite floats for the contract.
            fe_vals = np.where(np.isnan(fe_vals), 0.0, fe_vals)
            flux_err_list = fe_vals.tolist()

    return LightCurve(
        light_curve_id=lc_contract.light_curve_id,
        target_id=lc_contract.target_id,
        mission=lc_contract.mission,
        sector=lc_contract.sector,
        cadence=lc_contract.cadence,
        time=lk_lc.time.value.tolist(),
        flux=lk_lc.flux.value.tolist(),
        flux_error=flux_err_list,
        time_unit=lc_contract.time_unit,
        flux_unit=lc_contract.flux_unit,
        metadata={**lc_contract.metadata, "preprocessing": "adaptive"}
    )
