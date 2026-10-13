from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
import asyncio
import io
import csv
import os
import tempfile
import math

from app.contracts.models import LightCurve, DetectionCandidate, ClassifiedCandidate, Mission
from app.preprocessing.pipeline import preprocess_light_curve
from app.detection.bls import BLSDetector
from app.ml.classifier import ExoplanetClassifier
from app.validation.rules import validate_candidate, ValidationResult
from app.planet_properties.estimator import estimate_properties, PlanetProperties
from app.ranking.ops import calculate_ops, rank_candidates, OPSResult
from app.explainability.shap_wrapper import ShapExplainer, ShapExplanation
from app.reports.pdf import generate_scientific_report
from app.ingestion.service import IngestionService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Global dependencies
classifier_instance = None
explainer_instance = None

def get_classifier():
    global classifier_instance
    if classifier_instance is None:
        classifier_instance = ExoplanetClassifier()
    return classifier_instance

def get_explainer(classifier: ExoplanetClassifier = Depends(get_classifier)):
    global explainer_instance
    if explainer_instance is None:
        explainer_instance = ShapExplainer(classifier.model)
    return explainer_instance

class IngestRequest(BaseModel):
    target: str
    mission: str # 'TESS', 'Kepler'
    sector_or_quarter: Optional[int] = None

class DetectRequest(BaseModel):
    light_curve: LightCurve
    min_period: float = 1.0
    max_period: float = 20.0

@router.post("/ingest", response_model=LightCurve)
def ingest_data(request: IngestRequest):
    """Ingests a light curve from a mission archive."""
    service = IngestionService()
    try:
        if request.mission.upper() == "TESS":
            lc = service.download_tess(request.target, sector=request.sector_or_quarter)
        elif request.mission.upper() == "KEPLER":
            lc = service.download_kepler(request.target, quarter=request.sector_or_quarter)
        else:
            raise HTTPException(status_code=400, detail="Unsupported mission")
        return lc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/preprocess", response_model=LightCurve)
def preprocess(light_curve: LightCurve):
    """Preprocesses a light curve (removes NaNs, detrends, normalizes)."""
    try:
        return preprocess_light_curve(light_curve)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/detect", response_model=List[DetectionCandidate])
def detect_candidates(request: DetectRequest):
    """Runs Box Least Squares transit detection."""
    try:
        detector = BLSDetector(min_period=request.min_period, max_period=request.max_period)
        return detector.detect(request.light_curve)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/classify", response_model=ClassifiedCandidate)
def classify_candidate(
    candidate: DetectionCandidate,
    classifier: ExoplanetClassifier = Depends(get_classifier)
):
    """Classifies a detection candidate using the trained XGBoost model."""
    try:
        return classifier.predict(candidate)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate", response_model=ValidationResult)
def validate(candidate: ClassifiedCandidate):
    """Runs rule-based astrophysical false-positive validation."""
    try:
        return validate_candidate(candidate)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/properties", response_model=PlanetProperties)
def properties(candidate: DetectionCandidate):
    """Estimates planetary physical properties."""
    try:
        return estimate_properties(candidate)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/explain", response_model=ShapExplanation)
def explain(
    candidate: ClassifiedCandidate,
    explainer: ShapExplainer = Depends(get_explainer)
):
    """Provides SHAP explainability for the ML prediction."""
    try:
        return explainer.explain(candidate)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class OPSRequest(BaseModel):
    classified: ClassifiedCandidate
    props: PlanetProperties
    validation: ValidationResult

@router.post("/score", response_model=OPSResult)
def score_candidate(request: OPSRequest):
    """Calculates Observation Priority Score (OPS)."""
    try:
        return calculate_ops(request.classified, request.props, request.validation)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ReportRequest(BaseModel):
    classified: ClassifiedCandidate
    props: PlanetProperties
    ops_result: OPSResult
    validation: ValidationResult
    shap_explanation: ShapExplanation

@router.post("/report")
def generate_report(request: ReportRequest, background_tasks: BackgroundTasks):
    """Generates a scientific PDF report asynchronously and returns the path."""
    import os
    from uuid import uuid4
    try:
        os.makedirs("/tmp/asteria_reports", exist_ok=True)
        # We need a stable filename to return immediately
        pdf_filename = f"ASTERIA_Report_{request.classified.candidate.target_id}_{uuid4().hex[:6]}.pdf"
        pdf_path = os.path.join("/tmp/asteria_reports", pdf_filename)
        
        background_tasks.add_task(
            generate_scientific_report,
            request.classified,
            request.props,
            request.ops_result,
            request.validation,
            request.shap_explanation,
            "/tmp/asteria_reports",
            pdf_filename
        )
        return {"status": "queued", "report_path": pdf_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.responses import StreamingResponse

@router.post("/export/lightcurve/csv")
def export_lightcurve_csv(lc: LightCurve):
    """Exports a LightCurve to a CSV file."""
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        if lc.flux_error is not None:
            writer.writerow(["time", "flux", "flux_error"])
            for t, f, e in zip(lc.time, lc.flux, lc.flux_error):
                writer.writerow([t, f, e])
        else:
            writer.writerow(["time", "flux"])
            for t, f in zip(lc.time, lc.flux):
                writer.writerow([t, f])
                
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=lightcurve_{lc.target_id}.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

KNOWN_TESS_TARGETS = {
    "261136679": {
        "name": "Pi Mensae c",
        "type": "Super-Earth",
        "archetype": "sub_neptune",
        "stellar_mass": "0.84 M☉",
        "stellar_radius": "0.81 R☉",
        "temp": "1,150 K",
        "color": "#4B7BF5",
        "glow": "rgba(75, 123, 245, 0.6)",
    },
    "150428135": {
        "name": "TOI-700 d",
        "type": "Habitable-Zone Terrestrial",
        "archetype": "habitable_terrestrial",
        "stellar_mass": "0.42 M☉",
        "stellar_radius": "0.42 R☉",
        "temp": "269 K",
        "color": "#38bdf8",
        "glow": "rgba(56, 189, 248, 0.6)",
    },
    "100100827": {
        "name": "WASP-18 b",
        "type": "Ultra-Hot Jupiter",
        "archetype": "hot_jupiter",
        "stellar_mass": "1.22 M☉",
        "stellar_radius": "1.28 R☉",
        "temp": "2,700 K",
        "color": "#f59e0b",
        "glow": "rgba(245, 158, 11, 0.6)",
    },
    "259377017": {
        "name": "TOI-270 b",
        "type": "Resonant Super-Earth",
        "archetype": "sub_neptune",
        "stellar_mass": "0.38 M☉",
        "stellar_radius": "0.37 R☉",
        "temp": "528 K",
        "color": "#06b6d4",
        "glow": "rgba(6, 182, 212, 0.6)",
    },
    "22529346": {
        "name": "WASP-121 b",
        "type": "Scorching Evaporating Jupiter",
        "archetype": "scorched_gas_giant",
        "stellar_mass": "1.35 M☉",
        "stellar_radius": "1.46 R☉",
        "temp": "2,360 K",
        "color": "#ea580c",
        "glow": "rgba(234, 88, 12, 0.6)",
    },
    "410153553": {
        "name": "LHS 3844 b",
        "type": "Bare Rocky Lava Super-Earth",
        "archetype": "lava_rocky",
        "stellar_mass": "0.15 M☉",
        "stellar_radius": "0.19 R☉",
        "temp": "805 K",
        "color": "#ef4444",
        "glow": "rgba(239, 68, 68, 0.6)",
    },
    "355151781": {
        "name": "WASP-19 b",
        "type": "Ultra-Short Period Hot Jupiter",
        "archetype": "hot_jupiter",
        "stellar_mass": "0.97 M☉",
        "stellar_radius": "0.94 R☉",
        "temp": "2,050 K",
        "color": "#fbbf24",
        "glow": "rgba(251, 191, 36, 0.6)",
    },
    "410214986": {
        "name": "DS Tucanae A b",
        "type": "Young Ringed Planet (45 Myr)",
        "archetype": "young_ringed",
        "stellar_mass": "0.96 M☉",
        "stellar_radius": "0.87 R☉",
        "temp": "850 K",
        "color": "#8b5cf6",
        "glow": "rgba(139, 92, 246, 0.6)",
    },
    "261136680": {
        "name": "TIC 261136680 (Binary)",
        "type": "Eclipsing Binary (Control)",
        "archetype": "binary_star",
        "stellar_mass": "1.05 M☉",
        "stellar_radius": "1.10 R☉",
        "temp": "4,200 K",
        "color": "#ff3366",
        "glow": "rgba(255, 51, 102, 0.6)",
    }
}

PRESETS = {
    "pi-mensae-c": {
        "id": "pi-mensae-c",
        "name": "Pi Mensae c",
        "target_id": "TIC 261136679",
        "mission": "TESS",
        "sector": 1,
        "type": "Super-Earth",
        "archetype": "sub_neptune",
        "planet_radius": "2.04 R⊕",
        "period": "6.27 Days",
        "depth": "12,400 ppm",
        "temp": "1,150 K",
        "stellar_mass": "0.84 M☉",
        "stellar_radius": "0.81 R☉",
        "confidence": "94.2%",
        "verdict": "CONFIRMED CANDIDATE",
        "color": "#4B7BF5",
        "glow": "rgba(75, 123, 245, 0.6)",
        "description": "A close-in Super-Earth orbiting a bright naked-eye subgiant star discovered in TESS Sector 1."
    },
    "toi-700-d": {
        "id": "toi-700-d",
        "name": "TOI-700 d",
        "target_id": "TIC 150428135",
        "mission": "TESS",
        "sector": 11,
        "type": "Habitable-Zone Terrestrial",
        "archetype": "habitable_terrestrial",
        "planet_radius": "1.14 R⊕",
        "period": "37.42 Days",
        "depth": "850 ppm",
        "temp": "269 K",
        "stellar_mass": "0.42 M☉",
        "stellar_radius": "0.42 R☉",
        "confidence": "96.8%",
        "verdict": "CONFIRMED CANDIDATE",
        "color": "#38bdf8",
        "glow": "rgba(56, 189, 248, 0.6)",
        "description": "The first Earth-sized planet discovered in the optimistic habitable zone of an M-dwarf star by TESS."
    },
    "wasp-18-b": {
        "id": "wasp-18-b",
        "name": "WASP-18 b",
        "target_id": "TIC 100100827",
        "mission": "TESS",
        "sector": 2,
        "type": "Ultra-Hot Jupiter",
        "archetype": "hot_jupiter",
        "planet_radius": "13.9 R⊕",
        "period": "0.94 Days",
        "depth": "9,200 ppm",
        "temp": "2,700 K",
        "stellar_mass": "1.22 M☉",
        "stellar_radius": "1.28 R☉",
        "confidence": "99.4%",
        "verdict": "CONFIRMED CANDIDATE",
        "color": "#f59e0b",
        "glow": "rgba(245, 158, 11, 0.6)",
        "description": "An extreme scorching gas giant completing a full orbit in under 23 hours with a massive transit depth."
    },
    "toi-270-b": {
        "id": "toi-270-b",
        "name": "TOI-270 b",
        "target_id": "TIC 259377017",
        "mission": "TESS",
        "sector": 3,
        "type": "Resonant Super-Earth",
        "archetype": "sub_neptune",
        "planet_radius": "1.25 R⊕",
        "period": "3.36 Days",
        "depth": "1,850 ppm",
        "temp": "528 K",
        "stellar_mass": "0.38 M☉",
        "stellar_radius": "0.37 R☉",
        "confidence": "95.1%",
        "verdict": "CONFIRMED CANDIDATE",
        "color": "#06b6d4",
        "glow": "rgba(6, 182, 212, 0.6)",
        "description": "A resonant super-Earth orbiting an M3 dwarf in a multi-planet benchmark system discovered in Sector 3."
    },
    "wasp-121-b": {
        "id": "wasp-121-b",
        "name": "WASP-121 b",
        "target_id": "TIC 22529346",
        "mission": "TESS",
        "sector": 7,
        "type": "Scorching Evaporating Jupiter",
        "archetype": "scorched_gas_giant",
        "planet_radius": "18.7 R⊕",
        "period": "1.27 Days",
        "depth": "15,200 ppm",
        "temp": "2,360 K",
        "stellar_mass": "1.35 M☉",
        "stellar_radius": "1.46 R☉",
        "confidence": "99.8%",
        "verdict": "CONFIRMED CANDIDATE",
        "color": "#ea580c",
        "glow": "rgba(234, 88, 12, 0.6)",
        "description": "A tidally distorted hot Jupiter with glowing vaporized metals and water detected in its glowing stratosphere."
    },
    "lhs-3844-b": {
        "id": "lhs-3844-b",
        "name": "LHS 3844 b",
        "target_id": "TIC 410153553",
        "mission": "TESS",
        "sector": 1,
        "type": "Bare Rocky Lava Super-Earth",
        "archetype": "lava_rocky",
        "planet_radius": "1.32 R⊕",
        "period": "0.46 Days",
        "depth": "2,900 ppm",
        "temp": "805 K",
        "stellar_mass": "0.15 M☉",
        "stellar_radius": "0.19 R☉",
        "confidence": "97.4%",
        "verdict": "CONFIRMED CANDIDATE",
        "color": "#ef4444",
        "glow": "rgba(239, 68, 68, 0.6)",
        "description": "An atmosphere-less basalt rocky planet orbiting in just 11 hours with molten day-side lava features."
    },
    "wasp-19-b": {
        "id": "wasp-19-b",
        "name": "WASP-19 b",
        "target_id": "TIC 355151781",
        "mission": "TESS",
        "sector": 9,
        "type": "Ultra-Short Period Hot Jupiter",
        "archetype": "hot_jupiter",
        "planet_radius": "14.1 R⊕",
        "period": "0.79 Days",
        "depth": "19,800 ppm",
        "temp": "2,050 K",
        "stellar_mass": "0.97 M☉",
        "stellar_radius": "0.94 R☉",
        "confidence": "99.1%",
        "verdict": "CONFIRMED CANDIDATE",
        "color": "#fbbf24",
        "glow": "rgba(251, 191, 36, 0.6)",
        "description": "An ultra-short period gas giant skimming its parent star in a blistering 18.9-hour orbit."
    },
    "ds-tucanae-a-b": {
        "id": "ds-tucanae-a-b",
        "name": "DS Tucanae A b",
        "target_id": "TIC 410214986",
        "mission": "TESS",
        "sector": 1,
        "type": "Young Ringed Planet (45 Myr)",
        "archetype": "young_ringed",
        "planet_radius": "5.60 R⊕",
        "period": "8.14 Days",
        "depth": "4,100 ppm",
        "temp": "850 K",
        "stellar_mass": "0.96 M☉",
        "stellar_radius": "0.87 R☉",
        "confidence": "93.7%",
        "verdict": "CONFIRMED CANDIDATE",
        "color": "#8b5cf6",
        "glow": "rgba(139, 92, 246, 0.6)",
        "description": "A very young exoplanet still retaining its nascent circumplanetary disk and high stellar activity."
    },
    "tic-261136680": {
        "id": "tic-261136680",
        "name": "TIC 261136680 (Binary)",
        "target_id": "TIC 261136680",
        "mission": "TESS",
        "sector": 1,
        "type": "Eclipsing Binary (Control)",
        "archetype": "binary_star",
        "planet_radius": "Stellar Companion",
        "period": "1.83 Days",
        "depth": "45,000 ppm",
        "temp": "4,200 K",
        "stellar_mass": "1.05 M☉",
        "stellar_radius": "1.10 R☉",
        "confidence": "12.4%",
        "verdict": "FALSE POSITIVE",
        "color": "#ff3366",
        "glow": "rgba(255, 51, 102, 0.6)",
        "description": "Deep V-shaped mutual occultations characteristic of stellar eclipsing binaries, correctly rejected by ASTERIA."
    }
}

@router.post("/upload")
async def upload_fits_file(file: UploadFile = File(...)):
    """Uploads a TESS FITS file, parses it with Lightkurve, and executes AI inference."""
    filename = file.filename or "unknown.fits"
    if not (filename.lower().endswith(".fits") or filename.lower().endswith(".fit") or filename.lower().endswith(".fits.gz")):
        raise HTTPException(status_code=400, detail="Uploaded file must be a .fits or .fit file.")

    tmp_path = None
    try:
        suffix = ".fits.gz" if filename.lower().endswith(".fits.gz") else ".fits"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            if len(content) == 0:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")
            tmp.write(content)
            tmp_path = tmp.name

        service = IngestionService()
        lc = service.ingest_tess_file(tmp_path)
        
        # Extract stellar attributes from FITS header if present
        stellar_hdr = {}
        try:
            from astropy.io import fits
            with fits.open(tmp_path) as hdul:
                hdr = hdul[0].header
                stellar_hdr["ticid"] = str(hdr.get("TICID") or hdr.get("OBJECT") or "").replace("TIC", "").strip()
                stellar_hdr["teff"] = hdr.get("TEFF")
                stellar_hdr["radius"] = hdr.get("RADIUS")
                stellar_hdr["mass"] = hdr.get("MASS")
                stellar_hdr["sector"] = hdr.get("SECTOR")
        except Exception:
            pass

        # Run Preprocessing
        preprocessed = preprocess_light_curve(lc)
        
        # Run BLS Detection
        detector = BLSDetector(min_period=0.5, max_period=20.0)
        candidates = detector.detect(preprocessed)
        
        classifier = get_classifier()
        best_candidate = None
        classified_candidate = None
        properties = None
        validation = None
        
        if candidates and len(candidates) > 0:
            best_candidate = candidates[0]
            # Safely inject stellar parameters into candidate for property estimator
            try:
                rad_raw = float(stellar_hdr.get("radius") or 0)
                best_candidate.stellar_radius_solar = rad_raw if rad_raw > 0 else 1.0
            except (ValueError, TypeError):
                best_candidate.stellar_radius_solar = 1.0

            try:
                mass_raw = float(stellar_hdr.get("mass") or 0)
                best_candidate.stellar_mass_solar = mass_raw if mass_raw > 0 else 1.0
            except (ValueError, TypeError):
                best_candidate.stellar_mass_solar = 1.0

            try:
                teff_raw = float(stellar_hdr.get("teff") or 0)
                best_candidate.stellar_teff_k = teff_raw if teff_raw > 0 else 5778.0
            except (ValueError, TypeError):
                best_candidate.stellar_teff_k = 5778.0

            classified_candidate = classifier.predict(best_candidate)
            validation = validate_candidate(classified_candidate)
            properties = estimate_properties(best_candidate)

        # Resolve Target Name & Visual Archetype
        raw_tic = stellar_hdr.get("ticid") or str(lc.target_id).replace("TIC", "").strip()
        known_info = KNOWN_TESS_TARGETS.get(raw_tic)

        if known_info:
            planet_name = known_info["name"]
            planet_type = known_info["type"]
            archetype = known_info["archetype"]
            stellar_mass = known_info["stellar_mass"]
            stellar_radius = known_info["stellar_radius"]
            stellar_teff = known_info["temp"]
            color = known_info.get("color", "#4B7BF5")
            glow = known_info.get("glow", "rgba(75, 123, 245, 0.6)")
        else:
            planet_name = f"TIC {raw_tic}" if raw_tic else "Custom TESS Target"
            # Derive archetype safely from candidate physics
            depth_ppm = (best_candidate.depth * 1_000_000) if best_candidate else 0.0
            period = best_candidate.period_days if best_candidate else 5.0
            r_earth = properties.radius_earth if (properties and properties.radius_earth is not None) else 2.0
            eq_temp = properties.equilibrium_temperature_k if (properties and properties.equilibrium_temperature_k is not None) else 800.0

            if depth_ppm > 35_000:
                archetype = "binary_star"
                planet_type = "Eclipsing Binary Suspect"
                color, glow = "#ff3366", "rgba(255, 51, 102, 0.6)"
            elif (r_earth is not None and r_earth >= 10.0) or (depth_ppm > 8_000 and period < 3.0):
                archetype = "hot_jupiter"
                planet_type = "Ultra-Hot Gas Giant"
                color, glow = "#f59e0b", "rgba(245, 158, 11, 0.6)"
            elif (r_earth is not None and r_earth <= 1.5) and (eq_temp is not None and eq_temp < 350.0):
                archetype = "habitable_terrestrial"
                planet_type = "Habitable-Zone Terrestrial"
                color, glow = "#38bdf8", "rgba(56, 189, 248, 0.6)"
            elif (r_earth is not None and r_earth <= 1.8) and (eq_temp is not None and eq_temp >= 650.0):
                archetype = "lava_rocky"
                planet_type = "Scorched Lava Super-Earth"
                color, glow = "#ef4444", "rgba(239, 68, 68, 0.6)"
            else:
                archetype = "sub_neptune"
                planet_type = "Sub-Neptune / Super-Earth"
                color, glow = "#06b6d4", "rgba(6, 182, 212, 0.6)"

            # Stellar parameters from header or defaults
            def _format_teff(val):
                try:
                    v = float(val)
                    if math.isfinite(v) and v > 0:
                        return f"{int(v):,d} K"
                except (ValueError, TypeError):
                    pass
                return "5,778 K (Solar-Type)"

            def _format_radius(val):
                try:
                    v = float(val)
                    if math.isfinite(v) and v > 0:
                        return f"{v:.2f} R☉"
                except (ValueError, TypeError):
                    pass
                return "1.00 R☉"

            def _format_mass(val):
                try:
                    v = float(val)
                    if math.isfinite(v) and v > 0:
                        return f"{v:.2f} M☉"
                except (ValueError, TypeError):
                    pass
                return "1.00 M☉"

            stellar_teff = _format_teff(stellar_hdr.get("teff"))
            stellar_radius = _format_radius(stellar_hdr.get("radius"))
            stellar_mass = _format_mass(stellar_hdr.get("mass"))
            
        # Downsample for web chart performance
        total_pts = len(preprocessed.time)
        step = max(1, total_pts // 600)
        chart_time = [preprocessed.time[i] for i in range(0, total_pts, step)]
        chart_flux = [preprocessed.flux[i] for i in range(0, total_pts, step)]
        
        return {
            "status": "success",
            "filename": filename,
            "target_id": str(lc.target_id),
            "planet_name": planet_name,
            "planet_type": planet_type,
            "archetype": archetype,
            "color": color,
            "glow": glow,
            "mission": "TESS",
            "sector": stellar_hdr.get("sector") or lc.sector or 1,
            "total_points": total_pts,
            "time": chart_time,
            "flux": chart_flux,
            "has_candidate": best_candidate is not None,
            "period": f"{best_candidate.period_days:.2f} Days" if best_candidate else "--",
            "depth": f"{(best_candidate.depth * 1_000_000):.0f} ppm" if best_candidate else "--",
            "confidence": f"{(classified_candidate.planet_probability * 100):.1f}%" if classified_candidate else "N/A",
            "verdict": classified_candidate.prediction.value.replace("_", " ").upper() if classified_candidate else "NO TRANSIT DETECTED",
            "model_name": classified_candidate.model_name if classified_candidate else "ASTERIA-Pipeline",
            "is_synthetic": classified_candidate.metadata.get("is_synthetic_prediction", False) if classified_candidate else False,
            "stellar": {
                "mass": stellar_mass,
                "radius": stellar_radius,
                "temp": stellar_teff
            },
            "properties": {
                "radius": f"{properties.radius_earth:.2f} R⊕" if (properties and properties.radius_earth) else "Estimated",
                "temp": f"{properties.equilibrium_temperature_k:.0f} K" if (properties and properties.equilibrium_temperature_k) else "Unknown",
                "size_class": properties.size_class if properties else "Unknown",
            } if properties else {"radius": "Unknown", "temp": "Unknown", "size_class": "Unknown"},
            "validation": {
                "is_valid": validation.is_valid_astrophysically if validation else False,
            } if validation else {"is_valid": False}
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"FITS Processing Error: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

@router.get("/presets")
def get_presets():
    """Returns the list of curated pre-seeded targets for demo exploration."""
    return PRESETS

@router.get("/preset/{preset_id}")
def get_preset_detail(preset_id: str):
    """Returns details for a single pre-seeded target."""
    if preset_id not in PRESETS:
        raise HTTPException(status_code=404, detail="Preset target not found.")
    return PRESETS[preset_id]

from fastapi.responses import FileResponse

@router.get("/sample-fits")
def download_sample_fits():
    """Serves an authentic NASA TESS light curve FITS file for testing."""
    sample_path = "sample_data/tess_pi_mensae_c_lc.fits"
    if not os.path.exists(sample_path):
        sample_path = "sample_pi_mensae.fits"
    if not os.path.exists(sample_path):
        raise HTTPException(status_code=404, detail="Sample FITS file not found on server.")
    return FileResponse(
        path=sample_path,
        filename="tess2018206045859-s0001-0000000261136679-0120-s_lc.fits",
        media_type="application/fits",
    )
