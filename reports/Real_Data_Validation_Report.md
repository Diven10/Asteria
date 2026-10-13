# ASTERIA Real-Data Validation Report

## Executive Summary
This report summarizes the end-to-end processing of a real astronomical dataset (TESS Sector 1 observations of Pi Mensae, TIC 261136679). This execution validates the ingestion, adaptive preprocessing, Box Least Squares (BLS) detection, feature engineering, and hybrid validation systems.

**Disclaimer:** This is a *Detection Candidate* derived from algorithmic feature extraction. A BLS periodic dip is insufficient to definitively confirm an exoplanet without full astrophysical validation, spectroscopic follow-up, and catalog cross-matching. 

---

## 1. Pipeline Stages Validated
- **Real TESS FITS Ingestion:** Successfully downloaded and parsed Sector 1 target pixel/lightcurve files for TIC 261136679 via MAST (`lightkurve`). Handled `astropy.time.Time` extraction anomalies effectively.
- **Adaptive Preprocessing:** Removed NaNs, normalized the lightcurve, safely clipped high-sigma outliers without destroying the transit, and smoothed the data using a rolling detrending window.
- **BLS Execution:** Successfully scanned the preprocessed real light curve.
- **Feature Extraction:** Extracted period, depth, duration, SNR, and BLS Power.
- **Catalog Enrichment (TIC/CTL):** Attempted local lookup. Since the massive full-sky TIC v8 is not stored locally in this environment, stellar parameters were safely explicitly marked as `None` without fabricating values.
- **End-to-End Processing:** Generated XGBoost classifications, rule-based validation, and a full scientific PDF report without crashing on missing data.

---

## 2. Detection Results & Metrics

| Metric | Measured Value | Notes |
| :--- | :--- | :--- |
| **Target ID** | `261136679` (Pi Mensae) | Successfully matched TESS Input Catalog |
| **Mission / Sector** | TESS (Sector 1) | |
| **Period** | 6.270 days | Successfully recovered the known ~6.2679 day period of Pi Mensae c |
| **Depth** | 0.000059 | Fractional depth (approx 59 ppm). |
| **Duration** | 2.78 hours | Extracted transit duration (known is ~2.9 hours) |
| **BLS Power** | 89.65 | Strong peak in the periodogram |
| **Signal-to-Noise (SNR)** | 13.239 | Represents a high-confidence signal extraction |

## 3. Astrophysical Validation & Classification

### Available Catalog Parameters
- **Stellar Radius ($R_\odot$):** `None`
- **Stellar Mass ($M_\odot$):** `None`
- **Effective Temperature ($T_{eff}$):** `None`

*Note: The local catalog subset did not contain TIC 261136679. The pipeline correctly preserved `None` rather than fabricating synthetic astrophysical data.*

### Model Inference
- **XGBoost Classifier Prediction:** `PLANET_CANDIDATE`
- **Machine Learning Probability:** `0.8000` (80.0%)
*Caveat: The model classifies the transit morphology as highly planet-like, but this is a heuristic statistical measure, not an astrophysical confirmation.*

### Hybrid Validation
- **Validation Result:** `Invalid`
- **Fused Probability Score:** `0.0800` (8.0%)
- **Observation Priority Score (OPS):** `8.219`
*Reasoning: The hybrid rule engine heavily penalized the candidate due to the absence of stellar catalog parameters. Without a known stellar radius, it is impossible to definitively bound the planetary radius to physical limits (e.g., distinguishing a hot Jupiter from an eclipsing binary dwarf). Therefore, the system safely flagged the candidate as "Invalid" for automatic confirmation.*

---
**Conclusion:** 
ASTERIA correctly identified the morphological signature of a known exoplanet (Pi Mensae c) from raw TESS telemetry, successfully characterizing its period and duration. Crucially, the system correctly refused to automatically label it a "confirmed exoplanet" because the necessary physical stellar constraints were missing from the local catalog—demonstrating strict adherence to scientific rigor.
