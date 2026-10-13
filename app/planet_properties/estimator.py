import math
from dataclasses import dataclass
from app.contracts.models import DetectionCandidate

@dataclass
class PlanetProperties:
    """Estimated physical properties of a planet candidate."""
    radius_earth: float | None = None
    semi_major_axis_au: float | None = None
    equilibrium_temperature_k: float | None = None
    insolation_flux_earth: float | None = None
    size_class: str = "Unknown"
    habitable_zone_proxy: bool = False

def estimate_properties(candidate: DetectionCandidate) -> PlanetProperties:
    """
    Estimates planetary properties from transit and host-star parameters.
    Missing stellar parameters cleanly yield None without fabricating data.
    Invalid/unphysical parameters (e.g., negative mass) also yield None.

    Astrophysical assumptions and constants:
    - R_sun in Earth radii = 109.1
    - 1 AU in Solar Radii = 214.94
    - Solar Teff = 5778 K
    - Bond Albedo (A) assumed = 0.3 (rocky/Earth-like proxy)
    
    Equations:
    - Planet Radius (R_p): R_p = R_s * sqrt(depth)
    - Semi-major axis (a): a^3 = M_s * P^2 (Kepler's 3rd Law, P in years, M_s in solar masses, a in AU)
    - Equilibrium Temp (T_eq): T_eq = T_eff * sqrt(R_s / (2 * a)) * (1 - A)^0.25
    - Insolation Flux (S): S = (T_eff / 5778)^4 * (R_s / a)^2
    """
    props = PlanetProperties()
    
    # Needs stellar radius to compute planet radius
    if (
        candidate.stellar_radius_solar is not None 
        and candidate.stellar_radius_solar > 0 
        and candidate.depth >= 0
    ):
        # Rp = Rs * sqrt(depth)
        # Rs is in solar radii, Rp should be in Earth radii
        ratio = math.sqrt(candidate.depth)
        props.radius_earth = candidate.stellar_radius_solar * 109.1 * ratio
        
        # Classification thresholds
        if props.radius_earth < 1.25:
            props.size_class = "Sub-Earth" if props.radius_earth < 0.8 else "Earth-size"
        elif props.radius_earth < 2.0:
            props.size_class = "Super-Earth"
        elif props.radius_earth < 6.0:
            props.size_class = "Sub-Neptune"
        elif props.radius_earth < 15.0:
            props.size_class = "Gas Giant"
        else:
            props.size_class = "Super-Jupiter"
            
    # Needs stellar mass to compute semi-major axis
    if (
        candidate.stellar_mass_solar is not None 
        and candidate.stellar_mass_solar > 0 
        and candidate.period_days > 0
    ):
        # Kepler's 3rd Law: a = (M * P^2)^(1/3) where P is in years
        period_years = candidate.period_days / 365.25
        props.semi_major_axis_au = (candidate.stellar_mass_solar * (period_years ** 2)) ** (1/3)
        
    # Needs Teff, R_s, and a to compute Temp and Flux
    if (
        candidate.stellar_teff_k is not None 
        and candidate.stellar_teff_k > 0
        and candidate.stellar_radius_solar is not None 
        and candidate.stellar_radius_solar > 0
        and props.semi_major_axis_au is not None
        and props.semi_major_axis_au > 0
    ):
        # Convert 'a' from AU to solar radii
        a_solar = props.semi_major_axis_au * 214.94
        
        # Equilibrium Temperature
        # T_eq = T_eff * sqrt(Rs / (2*a)) * (1-A)^0.25 (assuming A = 0.3)
        props.equilibrium_temperature_k = candidate.stellar_teff_k * math.sqrt(
            candidate.stellar_radius_solar / (2 * a_solar)
        ) * (0.7 ** 0.25)
        
        # Insolation Flux (relative to Earth)
        # S_inc / S_earth = (T_eff / T_sun)^4 * (R_s / a_au)^2
        props.insolation_flux_earth = ((candidate.stellar_teff_k / 5778.0) ** 4) * (
            (candidate.stellar_radius_solar / props.semi_major_axis_au) ** 2
        )
        
        # Habitable Zone proxy (Conservative: 200K < Teq < 320K)
        if 200 < props.equilibrium_temperature_k < 320:
            props.habitable_zone_proxy = True

    return props
