from typing import List
from pydantic import BaseModel, Field
from app.contracts.models import ClassifiedCandidate
from app.planet_properties.estimator import PlanetProperties
from app.validation.rules import ValidationResult

class OPSConfig(BaseModel):
    """
    Observation Priority Score (OPS) configuration.
    Since exact scientific weights were not strictly provided in the ASTERIA source,
    these are engineering assumptions designed to be easily configurable.
    """
    weight_confidence: float = 40.0
    weight_snr: float = 20.0
    weight_radius: float = 20.0
    weight_host_star: float = 20.0
    
    snr_cap: float = 20.0
    fp_penalty_multiplier: float = 0.5  # applied to the total score if astrophysical validation fails
    
    # Radius tiers (R_earth)
    radius_earth_ideal_max: float = 2.0
    radius_earth_acceptable_max: float = 6.0
    
    # Teff tiers
    teff_m_dwarf_max: float = 4000.0
    teff_k_dwarf_max: float = 5000.0
    teff_g_dwarf_max: float = 6000.0

class OPSBreakdown(BaseModel):
    """Transparent explanation of the score components."""
    confidence_score: float
    snr_score: float
    radius_score: float
    host_star_score: float
    fp_penalty_applied: bool

class OPSResult(BaseModel):
    """Structured ranking output for a candidate."""
    candidate_id: str
    target_id: str
    period_days: float # secondary sort key for deterministic ranking ties
    total_score: float
    breakdown: OPSBreakdown
    heuristic_note: str = "Engineering heuristic priority metric; not an empirically calibrated validation score."


def calculate_ops(
    classified: ClassifiedCandidate, 
    props: PlanetProperties, 
    validation: ValidationResult,
    config: OPSConfig = OPSConfig()
) -> OPSResult:
    """
    Calculates Observation Priority Score (OPS) with a transparent breakdown.
    Scores theoretically range from 0 to 100.
    """
    # 1. Confidence score (normalized to weight_confidence)
    prob = validation.fused_probability
    confidence_score = prob * config.weight_confidence
    
    # 2. SNR score (normalized to weight_snr, assuming cap is 100% of weight)
    snr = classified.candidate.snr or 0.0
    capped_snr = min(config.snr_cap, snr)
    snr_score = (capped_snr / config.snr_cap) * config.weight_snr if config.snr_cap > 0 else 0.0
    
    # 3. Radius score (bonus for Earth/Super-Earth)
    radius_score = 0.0
    if props.radius_earth:
        if 0.5 < props.radius_earth < config.radius_earth_ideal_max:
            radius_score = config.weight_radius
        elif config.radius_earth_ideal_max <= props.radius_earth < config.radius_earth_acceptable_max:
            radius_score = config.weight_radius * 0.5
            
    # 4. Host-star suitability (bonus for M/K dwarfs)
    host_star_score = 0.0
    teff = classified.candidate.stellar_teff_k
    if teff:
        if teff < config.teff_m_dwarf_max:
            host_star_score = config.weight_host_star
        elif teff < config.teff_k_dwarf_max:
            host_star_score = config.weight_host_star * 0.75
        elif teff < config.teff_g_dwarf_max:
            host_star_score = config.weight_host_star * 0.5
            
    # Combine
    raw_score = confidence_score + snr_score + radius_score + host_star_score
    
    # 5. False-positive penalty
    fp_penalty_applied = not validation.is_valid_astrophysically
    if fp_penalty_applied:
        raw_score *= config.fp_penalty_multiplier
        
    total_score = min(100.0, max(0.0, raw_score))
    
    return OPSResult(
        candidate_id=str(classified.candidate.candidate_id),
        target_id=classified.candidate.target_id,
        period_days=classified.candidate.period_days,
        total_score=total_score,
        breakdown=OPSBreakdown(
            confidence_score=confidence_score,
            snr_score=snr_score,
            radius_score=radius_score,
            host_star_score=host_star_score,
            fp_penalty_applied=fp_penalty_applied
        )
    )

def rank_candidates(candidates: List[OPSResult]) -> List[OPSResult]:
    """
    Ranks candidates deterministically.
    Primary sort: total_score (descending)
    Secondary sort: period_days (ascending)
    Tertiary sort: target_id (ascending)
    """
    return sorted(
        candidates,
        key=lambda x: (-x.total_score, x.period_days, x.target_id)
    )
