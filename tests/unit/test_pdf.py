import os
import pytest
from uuid import uuid4
try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

from app.contracts.models import DetectionCandidate, ClassifiedCandidate, Mission, PredictionLabel
from app.planet_properties.estimator import PlanetProperties
from app.validation.rules import ValidationResult, RuleResult
from app.ranking.ops import OPSResult, OPSBreakdown
from app.explainability.shap_wrapper import ShapExplanation
from app.reports.pdf import generate_scientific_report

def build_mock_candidate():
    cand = DetectionCandidate.model_construct(
        candidate_id=uuid4(),
        light_curve_id=uuid4(),
        target_id="TIC 12345",
        mission=Mission.TESS,
        sector=14,
        period_days=5.0,
        epoch_btjd=10.0,
        duration_hours=2.0,
        depth=0.01,
        bls_power=100.0,
        snr=15.0,
        transit_count=5,
        stellar_radius_solar=1.0,
        stellar_mass_solar=1.0,
        stellar_teff_k=5778
    )
    return ClassifiedCandidate.model_construct(
        candidate=cand,
        prediction=PredictionLabel.PLANET_CANDIDATE,
        planet_probability=0.85,
        model_name="ASTERIA-Mock",
        model_version="1.0",
        feature_schema_version="2.0",
        features={"depth": 0.01, "snr": 15.0}
    )

def test_generate_scientific_report(tmp_path):
    classified = build_mock_candidate()
    
    props = PlanetProperties(
        radius_earth=1.0, 
        semi_major_axis_au=0.05, 
        equilibrium_temperature_k=300.0,
        insolation_flux_earth=1.2,
        size_class="Earth-size", 
        habitable_zone_proxy=True
    )
    
    validation = ValidationResult(
        is_valid_astrophysically=True, 
        fused_probability=0.85, 
        rules=[
            RuleResult(rule_name="TestRule", passed=True, reason="Looks good", is_missing_data=False)
        ]
    )
    
    ops = OPSResult(
        candidate_id=str(classified.candidate.candidate_id),
        target_id="TIC 12345",
        period_days=5.0,
        total_score=85.0,
        breakdown=OPSBreakdown(
            confidence_score=34.0, snr_score=15.0, radius_score=20.0, host_star_score=16.0, fp_penalty_applied=False
        )
    )
    
    shap = ShapExplanation(
        is_valid=True,
        feature_contributions={"depth": 0.5, "snr": 0.3},
        base_value=-2.0,
        predicted_value=1.5,
        feature_schema_version="2.0",
        model_name="ASTERIA-Mock",
        model_version="1.0"
    )
    
    out_dir = str(tmp_path)
    pdf_path = generate_scientific_report(classified, props, ops, validation, shap, output_dir=out_dir)
    
    assert os.path.exists(pdf_path)
    assert pdf_path.endswith("ASTERIA_Report_TIC_12345.pdf")
    
    # Simple check on file size
    assert os.path.getsize(pdf_path) > 1000  # Should be a reasonable PDF file
    
    if PYPDF_AVAILABLE:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
            
        assert "ASTERIA Scientific Report" in text
        assert "TIC 12345" in text
        assert "TESS" in text
        assert "ASTERIA-Mock" in text
        assert "TestRule" in text
        assert "Disclaimer" in text
        assert "depth" in text # SHAP feature

def test_generate_scientific_report_missing_data(tmp_path):
    classified = build_mock_candidate()
    classified.candidate.snr = None
    classified.candidate.stellar_teff_k = None
    
    props = PlanetProperties(
        radius_earth=None, 
        semi_major_axis_au=None, 
        equilibrium_temperature_k=None,
        insolation_flux_earth=None,
        size_class="Unknown", 
        habitable_zone_proxy=False
    )
    
    validation = ValidationResult(
        is_valid_astrophysically=True, 
        fused_probability=0.85, 
        rules=[]
    )
    
    ops = OPSResult(
        candidate_id=str(classified.candidate.candidate_id),
        target_id="TIC 12345",
        period_days=5.0,
        total_score=34.0,
        breakdown=OPSBreakdown(
            confidence_score=34.0, snr_score=0.0, radius_score=0.0, host_star_score=0.0, fp_penalty_applied=False
        )
    )
    
    shap = ShapExplanation(
        is_valid=False,
        error_message="SHAP model failed to load."
    )
    
    pdf_path = generate_scientific_report(classified, props, ops, validation, shap, output_dir=str(tmp_path))
    assert os.path.exists(pdf_path)
    
    if PYPDF_AVAILABLE:
        reader = PdfReader(pdf_path)
        text = "".join([p.extract_text() for p in reader.pages])
        assert "Unavailable" in text
        assert "SHAP Unavailable" in text
