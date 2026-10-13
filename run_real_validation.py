import os
from app.ingestion.service import IngestionService
from app.preprocessing.pipeline import preprocess_light_curve
from app.detection.bls import BLSDetector
from app.ml.classifier import ExoplanetClassifier
from app.validation.rules import validate_candidate
from app.planet_properties.estimator import estimate_properties
from app.ranking.ops import calculate_ops
from app.explainability.shap_wrapper import ShapExplainer
from app.reports.pdf import generate_scientific_report
from app.catalog.tic_ctl import TicCtlCatalog
import json

# 1. Ingest real TESS data
print("Ingesting TESS data...")
service = IngestionService()
lc = service.download_tess("Pi Mensae", sector=1)

print(f"Target: {lc.target_id}")

# 2. Preprocess
print("Preprocessing...")
processed_lc = preprocess_light_curve(lc)

# 3. Detect
print("Running BLS...")
detector = BLSDetector(min_period=1.0, max_period=10.0)
candidates = detector.detect(processed_lc)
print(f"Found {len(candidates)} candidates.")

if len(candidates) > 0:
    cand = candidates[0]
    
    classifier = ExoplanetClassifier()
    explainer = ShapExplainer(classifier.model)
    
    from app.api.pipeline import get_catalog_resolver
    catalog_reader, catalog_name = get_catalog_resolver()
    if catalog_reader is not None:
        record = catalog_reader.find_tic(cand.target_id)
        if record is not None:
            if record.stellar_radius_solar is not None: cand.stellar_radius_solar = record.stellar_radius_solar
            if record.stellar_mass_solar is not None: cand.stellar_mass_solar = record.stellar_mass_solar
            if record.teff_k is not None: cand.stellar_teff_k = record.teff_k
            cand.metadata["catalog_source"] = catalog_name

    classified = classifier.predict(cand)
    val_results = validate_candidate(classified)
    props = estimate_properties(cand)
    ops_res = calculate_ops(classified, props, val_results)
    shap_res = explainer.explain(classified)
    
    print("--- REAL DATA VALIDATION RESULTS ---")
    print(f"Target ID: {cand.target_id}")
    print(f"Mission: {cand.mission}")
    print(f"Period: {cand.period_days:.3f} days")
    print(f"Depth: {cand.depth:.6f}")
    print(f"Duration: {cand.duration_hours:.2f} hours")
    print(f"BLS Power: {cand.bls_power:.2f}")
    print(f"SNR: {cand.snr}")
    print(f"Catalog parameters available: Rs={cand.stellar_radius_solar}, Ms={cand.stellar_mass_solar}, Teff={cand.stellar_teff_k}")
    print(f"Classifier prediction: {classified.prediction}, prob={classified.planet_probability:.4f}")
    print(f"Validation result: {'Valid' if val_results.is_valid_astrophysically else 'Invalid'}, score={val_results.fused_probability:.4f}")
    print(f"OPS: {ops_res.total_score}")
    
    generate_scientific_report(classified, props, ops_res, val_results, shap_res, output_dir=".")
    print("PDF generated.")
else:
    print("No candidates found.")
