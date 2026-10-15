import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from app.ingestion.service import IngestionService
from app.preprocessing.pipeline import preprocess_light_curve
from app.detection.bls import BLSDetector
import argparse
import sys
from app.features.engineering import build_feature_vector, FEATURE_SCHEMA_VERSION
from app.ml.dataset_trainer import CANONICAL_FEATURES, DatasetTrainerConfig, train_from_dataset

def main():
    parser = argparse.ArgumentParser(description="ASTERIA Model Training Script")
    parser.add_argument("--data-path", type=str, default=None, help="Path to real astronomical feature dataset (CSV or Parquet)")
    parser.add_argument("--output-model-path", type=str, default="app/ml/models/baseline.joblib", help="Output path for model artifact")
    parser.add_argument("--target-id-col", type=str, default="target_id", help="Target ID column name")
    parser.add_argument("--label-col", type=str, default="label", help="Label column name")
    args = parser.parse_args()

    if args.data_path:
        print(f"Executing dataset-driven training on '{args.data_path}'...")
        cfg = DatasetTrainerConfig(
            data_path=args.data_path,
            output_model_path=args.output_model_path,
            target_id_col=args.target_id_col,
            label_col=args.label_col,
        )
        model, summary = train_from_dataset(cfg)
        print("Dataset-driven training completed successfully.")
        return

    print("Running demonstration baseline generation with simulated candidate features...")
    service = IngestionService()
    
    # 1. Fetch a known exoplanet host (Pi Mensae, TIC 261136679)
    print("Attempting to acquire TIC 261136679 (Known Planet)...")
    try:
        lc_planet = service.download_tess("TIC 261136679", sector=1)
    except Exception as e:
        print(f"Failed to acquire TIC 261136679, using synthetic baseline. {e}")
        lc_planet = None

    # 2. Fetch a known negative (Random star, TIC 261136680)
    print("Attempting to acquire TIC 261136680 (Negative Control)...")
    try:
        lc_neg = service.download_tess("TIC 261136680", sector=1)
    except Exception as e:
        print(f"Failed to acquire negative TIC, using synthetic baseline. {e}")
        lc_neg = None

    detector = BLSDetector(min_period=1.0, max_period=10.0)
    
    X_list = []
    y_list = []
    
    if lc_planet:
        print("Preprocessing and detecting transits on TIC 261136679...")
        lc_clean = preprocess_light_curve(lc_planet)
        candidates = detector.detect(lc_clean)
        if candidates:
            best = candidates[0]
            feats = build_feature_vector(best)
            X_list.append(feats)
            y_list.append(1)
            print(f"Extracted features for TIC 261136679: {feats}")
            
            # Demonstration augmentation
            for i in range(20):
                noisy_feats = feats.copy()
                for k, v in noisy_feats.items():
                    if pd.notna(v) and isinstance(v, (int, float)):
                        noisy_feats[k] = v * float(np.random.uniform(0.9, 1.1))
                X_list.append(noisy_feats)
                y_list.append(1)
                
    if lc_neg:
        print("Preprocessing and detecting transits on TIC 261136680...")
        lc_clean = preprocess_light_curve(lc_neg)
        candidates = detector.detect(lc_clean)
        if candidates:
            best = candidates[0]
            feats = build_feature_vector(best)
            X_list.append(feats)
            y_list.append(0)
            print(f"Extracted features for TIC 261136680: {feats}")
            
            # Demonstration augmentation
            for i in range(20):
                noisy_feats = feats.copy()
                for k, v in noisy_feats.items():
                    if pd.notna(v) and isinstance(v, (int, float)):
                        noisy_feats[k] = v * float(np.random.uniform(0.7, 1.3))
                X_list.append(noisy_feats)
                y_list.append(0)
                
    if not X_list:
        print("Notice: No live observations acquired. Generating synthetic demonstration baseline.")
        # Ensure all canonical features are present
        base_planet = {f: 0.0 for f in CANONICAL_FEATURES}
        base_planet.update({
            "period_days": 4.0, "duration_hours": 2.5, "depth": 0.01,
            "bls_power": 120.0, "snr": 15.0, "transit_count": 5.0,
            "stellar_radius_solar": 1.0, "stellar_mass_solar": 1.0, "stellar_teff_k": 5778.0,
            "depth_scaled": 0.01, "semi_major_axis_au": 0.05
        })
        base_neg = {f: 0.0 for f in CANONICAL_FEATURES}
        base_neg.update({
            "period_days": 2.0, "duration_hours": 1.2, "depth": 0.0005,
            "bls_power": 15.0, "snr": 2.5, "transit_count": 3.0,
            "stellar_radius_solar": 1.0, "stellar_mass_solar": 1.0, "stellar_teff_k": 5778.0,
            "depth_scaled": 0.0005, "semi_major_axis_au": 0.03
        })
        for _ in range(15):
            p_noisy = {k: v * float(np.random.uniform(0.95, 1.05)) if isinstance(v, (int, float)) and v > 0 else v for k, v in base_planet.items()}
            X_list.append(p_noisy)
            y_list.append(1)
            n_noisy = {k: v * float(np.random.uniform(0.90, 1.10)) if isinstance(v, (int, float)) and v > 0 else v for k, v in base_neg.items()}
            X_list.append(n_noisy)
            y_list.append(0)
        
    df = pd.DataFrame(X_list)
    # Ensure all canonical columns exist in canonical order
    for col in CANONICAL_FEATURES:
        if col not in df.columns:
            df[col] = 0.0
    df = df[CANONICAL_FEATURES].fillna(0)

    print("Fitting demonstration Random Forest Classifier on feature vector...")
    clf = RandomForestClassifier(n_estimators=50, random_state=42)
    clf.fit(df, y_list)

    # Clearly record non-scientific demonstration provenance
    clf.model_name = "ASTERIA-Demo-Baseline"
    clf.version = "0.1.0-DEMO"
    clf.feature_schema_version = FEATURE_SCHEMA_VERSION
    clf.is_synthetic = True
    clf.is_scientifically_trained = False
    clf.provenance = "synthetic_demonstration_baseline"
    clf.feature_names_in_ = np.array(CANONICAL_FEATURES)

    os.makedirs(os.path.dirname(os.path.abspath(args.output_model_path)), exist_ok=True)
    joblib.dump(clf, args.output_model_path)
    print(f"Demonstration model saved to {args.output_model_path}.")
    print("Scientific notice: Model is labeled as demonstration/synthetic baseline.")

if __name__ == "__main__":
    main()
