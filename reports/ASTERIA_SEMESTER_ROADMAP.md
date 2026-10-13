# ASTERIA Semester Roadmap

**Project Goal:** Build, evaluate, document, and scientifically validate an end-to-end exoplanet candidate detection system for noisy astronomical light curves.

---

## Phase 1: Verified Baseline (COMPLETED)
**Goal:** Establish a robust software architecture capable of processing light curves from raw data to a scientific report.
- **Files/Modules affected:** `app/ingestion/`, `app/preprocessing/`, `app/detection/`, `app/features/`, `app/api/`, `app/reports/`, `app/catalog/`
- **Expected output:** Complete, testable end-to-end pipeline with mock ML fallbacks.
- **Scientific risk:** None (baseline established without scientific claims).
- **Status:** **DONE** (75 tests passing, real TESS integration verified, API functional).

---

## Phase 2: Scientific Dataset Development
**Goal:** Design a reproducible dataset pipeline to construct tabular training data (features + labels) from raw TESS light curves using authoritative astronomical labels (NASA Exoplanet Archive / ExoFOP).
- **Files/Modules affected:** `app/ml/dataset_builder.py` (New), `scripts/build_dataset.py` (New)
- **Expected output:** A modular `DatasetBuilder` that accepts target lists, downloads light curves via Lightkurve, executes ASTERIA feature extraction, and persists `(X, y, groups)` to disk (e.g. Parquet/CSV).
- **Tests required:** `tests/unit/test_dataset_builder.py` (mocked downloads).
- **Scientific risk:** High (Label leakage, incorrect cross-matching, or API rate-limiting on bulk downloads).
- **Priority:** **URGENT** - First concrete implementation task.

---

## Phase 3: Scientific ML Training & Model Evaluation
**Goal:** Train the `ExoplanetClassifier` using the legitimate dataset created in Phase 2. Ensure rigorous evaluation using host-star group-aware cross-validation to prevent data leakage.
- **Files/Modules affected:** `app/ml/train.py`, `app/ml/evaluate.py` (New)
- **Expected output:** A scientifically trained `ASTERIA-XGBoost-Exoplanet.pkl` model, with versioned feature schemas, PR-AUC metrics, and explicitly labeled metadata.
- **Tests required:** Update `tests/unit/test_train.py` to handle the real data workflow gracefully in CI.
- **Scientific risk:** Moderate (Overfitting, class imbalance between planets and false positives).
- **Priority:** HIGH

---

## Phase 4: False Positive Analysis & Astrophysical Validation Tuning
**Goal:** Evaluate where the ML model fails and use the deterministic rule-based astrophysical validation (`app/validation/rules.py`) to catch specific edge cases (e.g. secondary eclipses, odd-even mismatches).
- **Files/Modules affected:** `app/validation/rules.py`, `scripts/evaluate_false_positives.py` (New)
- **Expected output:** Tuned thresholds for validation heuristics and a detailed False Positive / False Negative analysis report.
- **Tests required:** Edge case unit tests for validation rules based on real data failures.
- **Scientific risk:** Moderate (Heuristics might accidentally reject legitimate anomalous planets).
- **Priority:** MEDIUM

---

## Phase 5: Robustness & Explainability Experiments
**Goal:** Understand how the pipeline behaves under varying conditions (noise injection, missing stellar parameters) and map feature importance using SHAP.
- **Files/Modules affected:** `app/explainability/shap_wrapper.py`, `scripts/run_experiments.py` (New)
- **Expected output:** Documented experiments analyzing ASTERIA's sensitivity. SHAP summary plots identifying primary detection drivers.
- **Tests required:** Validating experiment runner scripts logic.
- **Scientific risk:** Low (Purely analytical phase).
- **Priority:** LOW (Late semester)

---

## Phase 6: Academic Documentation & Final Reporting
**Goal:** Compile the methodology, architecture, and scientific results into a defensible academic report.
- **Files/Modules affected:** `docs/`, `README.md`, `reports/Semester_Project_Report.md` (New)
- **Expected output:** Complete reproducible project documentation including dataset provenance, ML metrics, and architecture decisions.
- **Scientific risk:** Low
- **Priority:** LOW (End of semester)

---

### **FIRST CONCRETE IMPLEMENTATION TASK**
**Task:** Implement `app/ml/dataset_builder.py`
**Description:** Before we can train a model, we need the infrastructure to programmatically build the training dataset. The `DatasetBuilder` should take an input schema containing `target_id`, `mission`, `sector`, and `label` (e.g. Planet Candidate, False Positive). It will orchestrate the `IngestionService`, `preprocess_light_curve`, `BLSDetector`, and `build_feature_vector` modules to output a structured dataset DataFrame containing the extracted features, the target label, and the TIC ID for host-star grouping.
