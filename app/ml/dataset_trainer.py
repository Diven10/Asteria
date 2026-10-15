"""ASTERIA Dataset-Driven ML Training Pipeline.

Provides rigorous, schema-validated training on external astronomical datasets.
Enforces target-grouped splitting to prevent host-star data leakage, computes
held-out scientific metrics, preserves feature schema parity, and records complete
provenance metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit

try:
    from xgboost import XGBClassifier
except Exception:
    from sklearn.ensemble import RandomForestClassifier as XGBClassifier

from app.features.engineering import CANONICAL_FEATURES, FEATURE_SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_LABEL_MAPPING: dict[str, int] = {

    "CONFIRMED": 1,
    "CONFIRMED PLANET": 1,
    "CP": 1,
    "KP": 1,
    "KNOWN PLANET": 1,
    "PLANET": 1,
    "1": 1,
    "1.0": 1,
    "FALSE POSITIVE": 0,
    "FP": 0,
    "FA": 0,
    "FALSE ALARM": 0,
    "NON_PLANET": 0,
    "0": 0,
    "0.0": 0,
}


class DatasetValidationError(Exception):
    """Raised when an input dataset fails schema or data integrity validation."""


class IncompatibleDatasetError(DatasetValidationError):
    """Raised when an astronomical catalog lacks required transit/light curve features."""


@dataclass
class DatasetTrainerConfig:
    data_path: str | Path
    target_id_col: str = "target_id"
    host_star_id_col: Optional[str] = None
    label_col: str = "label"
    features: list[str] = field(default_factory=lambda: list(CANONICAL_FEATURES))
    label_mapping: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_LABEL_MAPPING))
    test_size: float = 0.2
    val_size: float = 0.1
    random_state: int = 42
    output_model_path: Optional[str] = None


def compute_file_sha256(filepath: str | Path) -> str:
    """Computes SHA-256 hash of a file for provenance tracking."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def detect_incompatible_catalogs(filepath: str | Path, first_lines: list[str]) -> None:
    """Detects known non-planetary catalogs to prevent fraudulent or mistaken training."""
    path_str = str(filepath).lower()
    
    # Check for TESS Candidate Target List (CTL)
    if "ctl" in path_str or any("planetcandidate" in line and "cooldwarfs" in line for line in first_lines[:5]):
        raise IncompatibleDatasetError(
            f"Dataset '{filepath}' appears to be the TESS Candidate Target List (CTL). "
            "The CTL is an observation prioritization catalog for stars, not an exoplanet disposition "
            "dataset. In CTL, 'planetcandidate' denotes stars prioritized for transit searches, "
            "not detected planets. It lacks transit light-curve features (period, depth, duration, SNR, etc.) "
            "and cannot be used to train an exoplanet transit classifier."
        )

    # Check for TESS Input Catalog (TIC) slices
    if "tic_dec" in path_str:
        raise IncompatibleDatasetError(
            f"Dataset '{filepath}' appears to be a TESS Input Catalog (TIC) declination slice. "
            "TIC files are source catalogs containing stellar properties, not labeled exoplanet candidates."
        )


def validate_and_load_dataset(
    config: DatasetTrainerConfig,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Loads and strictly validates an astronomical feature dataset."""
    filepath = Path(config.data_path)
    if not filepath.exists():
        raise DatasetValidationError(f"Dataset file does not exist: {filepath}")

    # Inspect first few lines for catalog detection
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        first_lines = [f.readline() for _ in range(10)]

    detect_incompatible_catalogs(filepath, first_lines)

    # Load data
    if filepath.suffix.lower() == ".parquet":
        df = pd.read_parquet(filepath)
    else:
        # Check if header is present
        df = pd.read_csv(filepath)

    if df.empty:
        raise DatasetValidationError(f"Dataset '{filepath}' is empty.")

    # Check for target/host star columns
    target_col = config.target_id_col
    if target_col not in df.columns:
        # Check common aliases
        aliases = ["tic_id", "ticid", "kepid", "target", "target_id", "hostname"]
        found = [c for c in aliases if c in df.columns]
        if found:
            target_col = found[0]
            df[config.target_id_col] = df[target_col]
        else:
            raise DatasetValidationError(
                f"Required target identifier column '{config.target_id_col}' not found. "
                f"Available columns: {list(df.columns)}"
            )

    host_star_col = config.host_star_id_col or target_col
    if host_star_col not in df.columns:
        df[host_star_col] = df[target_col]

    # Check label column
    label_col = config.label_col
    if label_col not in df.columns:
        label_aliases = ["authoritative_label", "disposition", "tfopwg_disp", "koi_disposition", "label"]
        found = [c for c in label_aliases if c in df.columns]
        if found:
            label_col = found[0]
            df[config.label_col] = df[label_col]
        else:
            raise DatasetValidationError(
                f"Required label column '{config.label_col}' not found. "
                f"Available columns: {list(df.columns)}"
            )

    # Normalize and map labels
    raw_labels = df[config.label_col].astype(str).str.strip().str.upper()
    mapped_labels = raw_labels.map(config.label_mapping)
    
    valid_mask = mapped_labels.notna()
    unmapped_count = int((~valid_mask).sum())
    
    if unmapped_count > 0:
        unmapped_samples = list(raw_labels[~valid_mask].unique())
        logger.warning(
            f"Filtered out {unmapped_count} records with ambiguous or unmapped labels: {unmapped_samples}"
        )

    df_clean = df[valid_mask].copy()
    df_clean["__clean_label__"] = mapped_labels[valid_mask].astype(int)

    if df_clean.empty:
        raise DatasetValidationError("No valid labeled records remaining after label mapping.")

    # Check class distribution
    class_counts = df_clean["__clean_label__"].value_counts().to_dict()
    if len(class_counts) < 2:
        raise DatasetValidationError(
            f"Training requires at least two classes. Found class distribution: {class_counts}"
        )

    # Map legacy secondary eclipse feature column if present
    if "secondary_eclipse_depth" not in df_clean.columns and "secondary_eclipse_power" in df_clean.columns:
        df_clean["secondary_eclipse_depth"] = df_clean["secondary_eclipse_power"]
    elif "secondary_eclipse_power" not in df_clean.columns and "secondary_eclipse_depth" in df_clean.columns:
        df_clean["secondary_eclipse_power"] = df_clean["secondary_eclipse_depth"]

    # Check available transit features
    available_features = [f for f in config.features if f in df_clean.columns]
    missing_features = [f for f in config.features if f not in df_clean.columns]


    # We must have at least the primary transit features to be a valid transit dataset
    core_transit_features = {"period_days", "depth", "duration_hours"}
    if not core_transit_features.intersection(set(available_features)):
        raise IncompatibleDatasetError(
            f"Dataset '{filepath}' lacks core transit features (period_days, depth, duration_hours). "
            f"Available columns: {list(df.columns)}"
        )

    # Missing value audit
    missingness = {f: float(df_clean[f].isna().mean()) for f in available_features}

    # Duplicate check
    duplicate_count = int(df_clean.duplicated(subset=[target_col] + available_features).sum())

    metadata = {
        "data_path": str(filepath.resolve()),
        "sha256": compute_file_sha256(filepath),
        "total_rows_loaded": len(df),
        "valid_rows_used": len(df_clean),
        "unmapped_rows_excluded": unmapped_count,
        "class_distribution": class_counts,
        "available_features": available_features,
        "missing_features": missing_features,
        "feature_missingness": missingness,
        "duplicate_rows": duplicate_count,
        "target_col": target_col,
        "host_star_col": host_star_col,
    }

    return df_clean, metadata


def train_from_dataset(config: DatasetTrainerConfig) -> tuple[Any, dict[str, Any]]:
    """Executes target-grouped training and evaluation on an astronomical feature dataset."""
    df, meta = validate_and_load_dataset(config)

    target_col = meta["target_col"]
    host_star_col = meta["host_star_col"]
    available_features = meta["available_features"]

    # Align to full canonical feature list (pad missing columns with NaN)
    X = df[available_features].copy()
    for col in config.features:
        if col not in X.columns:
            X[col] = np.nan
    X = X[config.features]

    y = df["__clean_label__"].to_numpy()
    groups = df[host_star_col].astype(str).to_numpy()

    # Target-grouped split to prevent leakage
    gss = GroupShuffleSplit(n_splits=1, test_size=config.test_size, random_state=config.random_state)
    train_idx, test_idx = next(gss.split(X, y, groups=groups))

    # Verify 0 leakage between train and test groups
    train_groups = set(groups[train_idx])
    test_groups = set(groups[test_idx])
    shared = train_groups.intersection(test_groups)
    assert len(shared) == 0, f"Critical leakage detected: {shared}"

    X_train, X_test = X.iloc[train_idx].copy(), X.iloc[test_idx].copy()
    y_train, y_test = y[train_idx], y[test_idx]

    # Preprocessing: compute imputation medians strictly on train
    train_medians = X_train.median(numeric_only=True).to_dict()

    # Train model
    is_xgb = XGBClassifier.__name__ == "XGBClassifier"
    if is_xgb:
        model = XGBClassifier(
            eval_metric="logloss",
            random_state=config.random_state,
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            missing=np.nan,
        )
        model.fit(X_train, y_train)
    else:
        # Fallback to Random Forest (fill NaNs strictly with train medians)
        X_train_filled = X_train.fillna(train_medians).fillna(0)
        X_test_filled = X_test.fillna(train_medians).fillna(0)
        model = XGBClassifier(
            random_state=config.random_state,
            n_estimators=100,
            max_depth=4,
        )
        model.fit(X_train_filled, y_train)

    # Evaluation on held-out test set
    if is_xgb:
        y_prob = model.predict_proba(X_test)[:, 1]
        y_pred = model.predict(X_test)
    else:
        y_prob = model.predict_proba(X_test_filled)[:, 1]
        y_pred = model.predict(X_test_filled)

    # Compute metrics safely
    try:
        p = float(precision_score(y_test, y_pred, zero_division=0))
        r = float(recall_score(y_test, y_pred, zero_division=0))
        f1 = float(f1_score(y_test, y_pred, zero_division=0))
    except Exception as e:
        logger.warning(f"Classification metric calculation issue: {e}")
        p, r, f1 = None, None, None

    try:
        cm = confusion_matrix(y_test, y_pred, labels=[0, 1]).tolist()
    except Exception:
        cm = None


    try:
        roc_auc = float(roc_auc_score(y_test, y_prob)) if len(np.unique(y_test)) > 1 else None
    except Exception:
        roc_auc = None

    try:
        pr_auc = float(average_precision_score(y_test, y_prob)) if len(np.unique(y_test)) > 1 else None
    except Exception:
        pr_auc = None

    eval_metrics = {
        "precision": p,
        "recall": r,
        "f1": f1,
        "confusion_matrix": cm,
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "test_samples": len(y_test),
        "train_samples": len(y_train),
        "test_target_groups": len(test_groups),
        "train_target_groups": len(train_groups),
    }

    # Model metadata attachment
    model_version = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    model.model_name = "ASTERIA-Dataset-Classifier"
    model.version = model_version
    model.feature_schema_version = FEATURE_SCHEMA_VERSION
    model.is_synthetic = False
    model.is_scientifically_trained = True

    model.provenance = {
        "dataset_path": str(Path(config.data_path).resolve()),
        "dataset_sha256": meta["sha256"],
        "split_strategy": "GroupShuffleSplit",
        "random_seed": config.random_state,
        "train_medians": train_medians,
        "metrics": eval_metrics,
    }

    # Persist model if requested
    saved_path = None
    if config.output_model_path:
        out_p = Path(config.output_model_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, out_p)
        saved_path = str(out_p.resolve())

    return model, {
        "metadata": meta,
        "metrics": eval_metrics,
        "model_version": model_version,
        "saved_path": saved_path,
    }


def main():
    parser = argparse.ArgumentParser(description="ASTERIA Dataset-Driven Model Training CLI")
    parser.add_argument("--data-path", type=str, required=True, help="Path to CSV or Parquet dataset")
    parser.add_argument("--target-id-col", type=str, default="target_id", help="Target ID column name")
    parser.add_argument("--host-star-id-col", type=str, default=None, help="Host star group column name")
    parser.add_argument("--label-col", type=str, default="label", help="Label column name")
    parser.add_argument("--output-model-path", type=str, default=None, help="Destination path for trained model")
    parser.add_argument("--test-size", type=float, default=0.2, help="Held-out test split fraction")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    cfg = DatasetTrainerConfig(
        data_path=args.data_path,
        target_id_col=args.target_id_col,
        host_star_id_col=args.host_star_id_col,
        label_col=args.label_col,
        output_model_path=args.output_model_path,
        test_size=args.test_size,
        random_state=args.random_state,
    )

    try:
        model, summary = train_from_dataset(cfg)
        print("Training succeeded:")
        print(json.dumps(summary, indent=2))
    except Exception as e:
        print(f"Training failed: {e}")
        raise


if __name__ == "__main__":
    main()
