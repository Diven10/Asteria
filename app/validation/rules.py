from dataclasses import dataclass, field
from app.contracts.models import ClassifiedCandidate
from typing import Dict, List, Any
import math

@dataclass
class ValidationConfig:
    odd_even_threshold: float = 0.1  # >10% diff in depth
    secondary_eclipse_threshold: float = 0.1 # secondary power > 10% of primary
    min_snr: float = 7.1
    max_depth: float = 0.05 # >5% depth is very likely an Eclipsing Binary
    max_radius_earth: float = 22.0 # ~2 Jupiter radii (brown dwarf boundary)

@dataclass
class RuleResult:
    rule_name: str
    passed: bool
    reason: str
    is_missing_data: bool = False

@dataclass
class ValidationResult:
    is_valid_astrophysically: bool
    fused_probability: float
    rules: List[RuleResult] = field(default_factory=list)
    validation_status: str = "VALIDATED"  # "VALIDATED", "INCONCLUSIVE", or "FAILED"
    is_inconclusive: bool = False
    untested_rule_count: int = 0

    def dict(self):
        return {
            "is_valid_astrophysically": self.is_valid_astrophysically,
            "fused_probability": self.fused_probability,
            "validation_status": self.validation_status,
            "is_inconclusive": self.is_inconclusive,
            "untested_rule_count": self.untested_rule_count,
            "rules": [r.__dict__ for r in self.rules]
        }

def validate_candidate(
    classified: ClassifiedCandidate, 
    config: ValidationConfig | None = None
) -> ValidationResult:
    """
    Applies astrophysical rule-based checks and fuses them with the ML score.
    Does not reduce everything to an unexplained boolean.
    """
    if config is None:
        config = ValidationConfig()
        
    candidate = classified.candidate
    rules = []
    
    # 1. Odd-even depth difference
    if candidate.odd_even_depth_difference is not None and candidate.depth > 0:
        ratio = candidate.odd_even_depth_difference / candidate.depth
        if ratio > config.odd_even_threshold:
            rules.append(RuleResult("odd_even", False, f"Difference ratio {ratio:.3f} > {config.odd_even_threshold}"))
        else:
            rules.append(RuleResult("odd_even", True, f"Difference ratio {ratio:.3f} within threshold"))
    else:
        rules.append(RuleResult("odd_even", True, "Missing odd-even data", is_missing_data=True))
        
    # 2. Secondary eclipse (occultation at half-orbital phase)
    # Statistic: depth_phased[0] from Astropy BoxLeastSquares.compute_stats()
    # Units: Dimensionless fractional flux depth (Delta F / F)
    # Sign convention: Positive for flux dips at phase 0.5; clamped to >= 0 for physical depth
    # Validation equation: ratio = delta_sec / delta_pri
    sec_depth = getattr(candidate, "secondary_eclipse_depth", None)
    if sec_depth is None:
        sec_depth = candidate.secondary_eclipse_power

    if sec_depth is not None and candidate.depth > 0:
        ratio = sec_depth / candidate.depth
        if ratio > config.secondary_eclipse_threshold:
            rules.append(RuleResult(
                "secondary_eclipse",
                False,
                f"Secondary eclipse depth ratio {ratio:.3f} > {config.secondary_eclipse_threshold}"
            ))
        else:
            rules.append(RuleResult(
                "secondary_eclipse",
                True,
                f"Secondary eclipse depth ratio {ratio:.3f} within threshold"
            ))
    elif sec_depth is not None and candidate.depth <= 0:
        rules.append(RuleResult("secondary_eclipse", False, "Primary transit depth non-positive"))
    else:
        rules.append(RuleResult("secondary_eclipse", True, "Missing secondary eclipse data", is_missing_data=True))

        
    # 3. SNR screening
    if candidate.snr is not None:
        if candidate.snr < config.min_snr:
            rules.append(RuleResult("snr", False, f"SNR {candidate.snr:.2f} < {config.min_snr}"))
        else:
            rules.append(RuleResult("snr", True, f"SNR {candidate.snr:.2f} >= {config.min_snr}"))
    else:
        rules.append(RuleResult("snr", True, "Missing SNR data", is_missing_data=True))
        
    # 4. V-shape / Deep transit proxy
    if candidate.depth > config.max_depth:
        rules.append(RuleResult("depth_v_shape", False, f"Transit depth {candidate.depth:.3f} exceeds planetary proxy {config.max_depth}"))
    else:
        rules.append(RuleResult("depth_v_shape", True, f"Transit depth {candidate.depth:.3f} is acceptable"))
        
    # 5. Impossibly large radius check (if stellar radius is available)
    if candidate.stellar_radius_solar is not None and candidate.stellar_radius_solar > 0:
        ratio = math.sqrt(candidate.depth)
        radius_earth = candidate.stellar_radius_solar * 109.1 * ratio
        if radius_earth > config.max_radius_earth:
            rules.append(RuleResult("planet_radius", False, f"Radius {radius_earth:.1f} R_earth > {config.max_radius_earth}"))
        else:
            rules.append(RuleResult("planet_radius", True, f"Radius {radius_earth:.1f} R_earth is acceptable"))
    else:
        rules.append(RuleResult("planet_radius", True, "Missing stellar radius for physical size check", is_missing_data=True))

    # Fusion and Scientific Status Resolution
    failed_rules = [r for r in rules if not r.passed]
    missing_rules = [r for r in rules if r.is_missing_data]
    is_valid = len(failed_rules) == 0
    
    if len(failed_rules) > 0:
        status = "FAILED"
        is_inconclusive = False
    elif len(missing_rules) > 0:
        status = "INCONCLUSIVE"
        is_inconclusive = True
    else:
        status = "VALIDATED"
        is_inconclusive = False

    fused_score = classified.planet_probability
    
    # Penalize probability heavily if astrophysical checks fail
    if not is_valid:
        penalty = 0.1 ** len(failed_rules)
        fused_score = fused_score * penalty

    return ValidationResult(
        is_valid_astrophysically=is_valid,
        fused_probability=fused_score,
        rules=rules,
        validation_status=status,
        is_inconclusive=is_inconclusive,
        untested_rule_count=len(missing_rules)
    )
