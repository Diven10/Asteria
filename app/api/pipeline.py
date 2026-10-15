from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import os

from app.contracts.models import LightCurve, Mission, Cadence
from app.preprocessing.pipeline import preprocess_light_curve
from app.detection.bls import BLSDetector
from app.ml.classifier import ExoplanetClassifier
from app.validation.rules import validate_candidate
from app.planet_properties.estimator import estimate_properties
from app.ranking.ops import calculate_ops, rank_candidates, OPSBreakdown
from app.explainability.shap_wrapper import ShapExplainer
from app.reports.pdf import generate_scientific_report

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

class PipelineRequest(BaseModel):
    light_curve: LightCurve
    min_period: float = 1.0
    max_period: float = 20.0
    generate_pdf: bool = False

class CandidateResult(BaseModel):
    target_id: str
    period_days: float
    depth: float
    planet_probability: float
    is_valid_astrophysically: bool
    ops_score: float
    ops_breakdown: OPSBreakdown
    size_class: str
    habitable_zone_proxy: bool
    pdf_report_path: Optional[str] = None
    validation_status: Optional[str] = None
    is_synthetic_prediction: Optional[bool] = None
    model_name: Optional[str] = None


from app.catalog.tic_ctl import TicCtlCatalog
from app.catalog.tic import TicCatalog

def get_catalog_resolver():
    """Returns the configured catalog reader and its source name."""
    tic_path = os.environ.get("ASTERIA_TIC_PATH")
    if tic_path and os.path.exists(tic_path):
        return TicCatalog(tic_path), "TIC_v8.1"
        
    ctl_path = os.environ.get("ASTERIA_CATALOG_PATH")
    if ctl_path and os.path.exists(ctl_path):
        return TicCtlCatalog(ctl_path), "CTL_v8.01"
        
    return None, None

@router.post("/analyze", response_model=List[CandidateResult])
async def run_pipeline(request: PipelineRequest):
    try:
        # 1. Preprocess
        processed_lc = preprocess_light_curve(request.light_curve)
        
        # 2. Detect
        detector = BLSDetector(min_period=request.min_period, max_period=request.max_period)
        candidates = detector.detect(processed_lc)
        
        # 3. Classify & Validate & Rank & Explain
        classifier = ExoplanetClassifier()
        explainer = ShapExplainer(classifier.model)
        catalog_reader, catalog_name = get_catalog_resolver()
        
        raw_results = []
        for cand in candidates:
            # TIC/CTL Host-Star Characterization
            if catalog_reader is not None:
                record = catalog_reader.find_tic(cand.target_id)
                if record is not None:
                    # Update candidate with known parameters
                    if record.stellar_radius_solar is not None:
                        cand.stellar_radius_solar = record.stellar_radius_solar
                    if record.stellar_mass_solar is not None:
                        cand.stellar_mass_solar = record.stellar_mass_solar
                    if record.teff_k is not None:
                        cand.stellar_teff_k = record.teff_k
                    cand.metadata["catalog_source"] = catalog_name
            
            classified = classifier.predict(cand)
            
            val_results = validate_candidate(classified)
            props = estimate_properties(cand)
            ops_res = calculate_ops(classified, props, val_results)
            shap_res = explainer.explain(classified)
            
            pdf_path = None
            if request.generate_pdf:
                # Store in /tmp or workspace for demo
                pdf_path = generate_scientific_report(
                    classified, props, ops_res, val_results, shap_res, output_dir="/tmp"
                )
                
            res = CandidateResult(
                target_id=cand.target_id,
                period_days=cand.period_days,
                depth=cand.depth,
                planet_probability=classified.planet_probability,
                is_valid_astrophysically=val_results.is_valid_astrophysically,
                ops_score=ops_res.total_score,
                ops_breakdown=ops_res.breakdown,
                size_class=props.size_class,
                habitable_zone_proxy=props.habitable_zone_proxy,
                pdf_report_path=pdf_path,
                validation_status=getattr(val_results, "validation_status", "VALIDATED"),
                is_synthetic_prediction=classified.metadata.get("is_synthetic_prediction", False),
                model_name=classified.model_name
            )

            raw_results.append((ops_res, res))
            
        # Deterministic Ranking
        ops_list = [r[0] for r in raw_results]
        ranked_ops = rank_candidates(ops_list)
        
        # Re-order the results based on ranked target IDs
        ranked_results = []
        for ranked_op in ranked_ops:
            for ops_res, res in raw_results:
                if ops_res.candidate_id == ranked_op.candidate_id:
                    ranked_results.append(res)
                    break
            
        return ranked_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
