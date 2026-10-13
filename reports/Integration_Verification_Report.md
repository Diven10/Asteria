# ASTERIA Integration Verification Report

## Issue 1: TIC Integration Resolved
The `/pipeline/analyze` orchestration flow has been updated to support reading and extracting physical stellar parameters directly from the 9.5GB TIC v8.1 database export, while retaining backwards compatibility with the legacy CTL CSV.

- **Configurable Paths:** The pipeline now correctly resolves `ASTERIA_TIC_PATH` (primary) and `ASTERIA_CATALOG_PATH` (fallback) via the `get_catalog_resolver()` function. 
- **Provenance Preservation:** Whichever catalog successfully matches the `target_id` is now explicitly recorded in `cand.metadata["catalog_source"]` (e.g., `"TIC_v8.1"` or `"CTL_v8.01"`), preserving data lineage for the final report without breaking the Pydantic schemas.
- **Contract Adherence:** Missing values in the catalog explicitly remain as `None`. No fabricated parameters are injected.

## Issue 2: Model Status Resolved
An exhaustive search of the workspace (`asteria_data/`, `tests/fixtures/`) confirmed that **legitimate labeled astronomical data (ground-truth exoplanet light curves) is NOT present**. Because no real data exists to train on, the system correctly refuses to fabricate scientific validity.

- **Scientific Transparency:** The training pipeline in `app/ml/train.py` was refactored. When evaluating its execution on synthetic testing data, it now explicitly skips calculating PR-AUC and other metrics, injecting `None` and an explicit `limitation` string into the output to prevent fabricating performance statistics.
- **Model Provenance:** The `test_train` pipeline now attaches the model name `ASTERIA-Untrained-Estimator` instead of pretending to be a scientifically validated XGBoost instance. 
- **Synthetic Fallbacks:** The classifier explicitly flags `is_synthetic_prediction = True` internally if the real model path is not supplied, allowing end-to-end integration testing to function without misleading end-users on the dashboard.

## Test Execution Summary
- **Tests Added:** `tests/integration/test_tic_enrichment.py`
- **Total Tests Passed:** 75 / 75
- **Coverage:** Complete integration of the `TicCatalog` class within the FastAPI lifecycle is now verified, successfully mocking a 125-column payload and confirming the dynamic extraction of `stellar_radius` leading to a valid `size_class`.

## Remaining Scientific Limitations
1. **Lack of Labeled Training Data:** The system's ML classification relies entirely on a deterministic rule-based synthetic fallback. Until a scientifically rigorous dataset (e.g., NASA Exoplanet Archive cross-matched TESS targets) is provided and run through `TrainingPipeline`, ASTERIA cannot generate accurate planet probabilities.
2. **O(N) Catalog Lookup Bottleneck:** The `TicCatalog` utilizes a lazy-loading streaming CSV reader to prevent RAM exhaustion. However, this causes linear time complexity $O(N)$ when searching for a `target_id`. Against the 9.5GB TIC v8.1 file, this will cause the dashboard to block heavily on large batches of candidates. This must be migrated to an indexed PostgreSQL table for production deployment.
