"""ASTERIA Real Labelled TESS Dataset Generation Pipeline.

Coordinates the end-to-end dataset generation:
1. Ingests authoritative TOI dispositions and orbital ephemerides from NASA Exoplanet Archive.
2. Acquires calibrated real TESS light curves via Lightkurve/MAST.
3. Preprocesses and runs Astropy Box Least Squares (BLS) transit detection.
4. Performs candidate-level ephemeris matching (fundamental, P/2, 2P harmonics, phase alignment).
5. Excludes unmatched, ambiguous, or poor-quality signals from supervised training.
6. Derives canonical Schema 2.0 features through ASTERIA's real inference feature engineering.
7. Generates auditable feature tables (Parquet/CSV) and an end-to-end provenance manifest.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.contracts.models import LightCurve, Mission
from app.detection.bls import BLSDetector
from app.features.engineering import (
    CANONICAL_FEATURES,
    FEATURE_METADATA,
    FEATURE_SCHEMA_VERSION,
    build_feature_vector,
)
from app.ingestion.service import IngestionService
from app.ml.authoritative_data import AuthoritativeTOICandidate, TOIAuthoritativeSource
from app.ml.dataset_builder import AuthoritativeTarget
from app.ml.signal_matcher import (
    CatalogEphemeris,
    MatchMethod,
    MatchStatus,
    SignalMatcher,
    SignalMatchResult,
)
from app.ml.tess_dataset import TESSAcquisitionLayer
from app.preprocessing.pipeline import preprocess_light_curve

logger = logging.getLogger(__name__)


def compute_bytes_sha256(data: bytes) -> str:
    """Computes SHA-256 hash of byte content."""
    sha = hashlib.sha256()
    sha.update(data)
    return sha.hexdigest()


def compute_file_sha256(filepath: str | Path) -> str:
    """Computes SHA-256 hash of a local file."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


@dataclass
class DatasetPipelineConfig:
    """Configuration for real dataset generation and auditing."""

    output_dir: str = "data/labelled_dataset"
    download_dir: Optional[str] = None
    pilot_positive: int = 5
    pilot_negative: int = 5
    pilot_ambiguous: int = 2
    specific_tic_ids: Optional[List[str]] = None
    period_tolerance: float = 0.03
    max_phase_offset: float = 0.05
    min_period: float = 1.0
    max_period: float = 20.0
    min_valid_samples: int = 50
    min_time_span_days: float = 2.0
    max_depth_threshold: float = 0.15


class TESSDatasetPipeline:
    """Orchestrates real TESS dataset creation, candidate matching, and auditing."""

    def __init__(
        self,
        config: Optional[DatasetPipelineConfig] = None,
        authoritative_source: Optional[TOIAuthoritativeSource] = None,
        acquisition_layer: Optional[TESSAcquisitionLayer] = None,
    ):
        self.config = config or DatasetPipelineConfig()
        self.source = authoritative_source or TOIAuthoritativeSource()
        ingestion_svc = IngestionService()
        self.acquisition = acquisition_layer or TESSAcquisitionLayer(
            ingestion_service=ingestion_svc,
            download_dir=self.config.download_dir,
        )
        self.matcher = SignalMatcher(
            period_tolerance=self.config.period_tolerance,
            max_phase_offset=self.config.max_phase_offset,
        )
        self.detector = BLSDetector(
            min_period=self.config.min_period,
            max_period=self.config.max_period,
        )

    def _assess_light_curve_quality(self, lc: LightCurve) -> Tuple[bool, Optional[str]]:
        """Assesses photometric time series quality before transit detection."""
        time_arr = np.asarray(lc.time, dtype=float)
        flux_arr = np.asarray(lc.flux, dtype=float)
        valid = np.isfinite(time_arr) & np.isfinite(flux_arr)

        if valid.sum() < self.config.min_valid_samples:
            return False, f"Insufficient valid cadences ({valid.sum()} < {self.config.min_valid_samples})."

        t_valid = time_arr[valid]
        span = float(t_valid.max() - t_valid.min())
        if span < self.config.min_time_span_days:
            return False, f"Time baseline span too short ({span:.2f} d < {self.config.min_time_span_days} d)."

        return True, None

    def run_pipeline(
        self,
        targets: Optional[List[AuthoritativeTarget]] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any], Dict[str, Any]]:
        """Executes dataset acquisition, transit extraction, ephemeris matching, and serialization.

        Returns:
            - features_df: DataFrame of derived features and labels.
            - manifest: Complete provenance manifest dictionary.
            - audit_summary: Summary metrics and scientific audit findings.
        """
        # 1. Acquire Authoritative Targets
        if targets is None:
            if self.config.specific_tic_ids:
                logger.info(f"Fetching specific TIC targets: {self.config.specific_tic_ids}")
                tics_str = ", ".join(f"'{tic}'" for tic in self.config.specific_tic_ids)
                raw_df = self.source._fetch_raw_data(where_clause=f"tid in ({tics_str})")
                result = self.source.process(raw_df, include_ambiguous=True)
                targets = result.targets
            else:
                logger.info(
                    f"Fetching pilot targets ({self.config.pilot_positive} pos, "
                    f"{self.config.pilot_negative} neg, {self.config.pilot_ambiguous} amb)..."
                )
                targets = self.source.fetch_pilot_targets(
                    n_positive=self.config.pilot_positive,
                    n_negative=self.config.pilot_negative,
                    n_ambiguous=self.config.pilot_ambiguous,
                )

        records_log: List[Dict[str, Any]] = []
        feature_rows: List[Dict[str, Any]] = []

        retrieved_count = 0
        failed_count = 0
        detected_signals_count = 0
        supervised_count = 0
        pos_count = 0
        neg_count = 0
        unmatched_count = 0
        excluded_count = 0
        exclusion_breakdown: Dict[str, int] = {}

        for target in targets:
            tic_id = str(target.target_id)
            known_candidates = [
                c.to_catalog_ephemeris() for c in target.candidates if c.to_catalog_ephemeris() is not None
            ]

            record_entry: Dict[str, Any] = {
                "tic_id": tic_id,
                "host_star_id": target.host_star_id or tic_id,
                "authoritative_target_label": target.authoritative_label,
                "known_candidates": [
                    {
                        "toi_id": c.toi_id,
                        "disposition": c.disposition,
                        "supervised_label": c.supervised_label,
                        "period_days": c.period_days,
                        "epoch_bjd": c.epoch_bjd,
                    }
                    for c in target.candidates
                ],
                "acquisition": {},
                "detection": {},
                "matching": {},
                "is_supervised": False,
                "supervised_label": None,
                "exclusion_reason": None,
            }

            # 2. Download Real Light Curve
            try:
                lc = self.acquisition.ingest(target)
                retrieved_count += 1
                record_entry["acquisition"] = {
                    "status": "SUCCESS",
                    "mission": lc.mission.value,
                    "sector": lc.sector,
                    "cadence": lc.cadence.value,
                    "samples_count": len(lc.time),
                    "time_unit": lc.time_unit,
                    "flux_unit": lc.flux_unit,
                }
            except Exception as e:
                failed_count += 1
                excluded_count += 1
                err_msg = f"Acquisition failed: {e}"
                record_entry["acquisition"] = {"status": "FAILED", "error": str(e)}
                record_entry["exclusion_reason"] = err_msg
                exclusion_breakdown["EXCLUDED_ACQUISITION_FAILED"] = (
                    exclusion_breakdown.get("EXCLUDED_ACQUISITION_FAILED", 0) + 1
                )
                records_log.append(record_entry)
                continue

            # 3. Quality Assessment
            quality_ok, quality_err = self._assess_light_curve_quality(lc)
            if not quality_ok:
                excluded_count += 1
                record_entry["exclusion_reason"] = quality_err
                exclusion_breakdown["EXCLUDED_DATA_QUALITY"] = (
                    exclusion_breakdown.get("EXCLUDED_DATA_QUALITY", 0) + 1
                )
                records_log.append(record_entry)
                continue

            # 4. Preprocess Light Curve
            try:
                clean_lc = preprocess_light_curve(lc)
            except Exception as e:
                excluded_count += 1
                err_msg = f"Preprocessing failed: {e}"
                record_entry["exclusion_reason"] = err_msg
                exclusion_breakdown["EXCLUDED_PREPROCESSING_FAILED"] = (
                    exclusion_breakdown.get("EXCLUDED_PREPROCESSING_FAILED", 0) + 1
                )
                records_log.append(record_entry)
                continue

            # 5. BLS Transit Detection
            candidates = self.detector.detect(clean_lc)
            if not candidates:
                excluded_count += 1
                record_entry["detection"] = {"status": "NO_SIGNALS_DETECTED"}
                record_entry["exclusion_reason"] = "No BLS candidates detected on light curve."
                exclusion_breakdown["EXCLUDED_NO_SIGNAL"] = (
                    exclusion_breakdown.get("EXCLUDED_NO_SIGNAL", 0) + 1
                )
                records_log.append(record_entry)
                continue

            detected_signals_count += len(candidates)
            # Evaluate the primary candidate
            best_cand = candidates[0]

            record_entry["detection"] = {
                "status": "SIGNAL_DETECTED",
                "period_days": best_cand.period_days,
                "epoch_btjd": best_cand.epoch_btjd,
                "duration_hours": best_cand.duration_hours,
                "depth": best_cand.depth,
                "bls_power": best_cand.bls_power,
                "snr": best_cand.snr,
                "transit_count": best_cand.transit_count,
                "secondary_eclipse_depth": best_cand.secondary_eclipse_depth,
            }

            # 6. Candidate-Level Signal Matching
            match_res: SignalMatchResult = self.matcher.match_candidate(
                detected_period=best_cand.period_days,
                detected_epoch_btjd=best_cand.epoch_btjd,
                detected_duration_hours=best_cand.duration_hours,
                catalog_candidates=known_candidates,
            )

            record_entry["matching"] = match_res.to_dict()

            # 7. Supervised Labeling and Exclusion Decision
            if not match_res.is_matched:
                unmatched_count += 1
                excluded_count += 1
                reason = match_res.exclusion_reason or "Detected signal did not match catalog ephemeris."
                record_entry["exclusion_reason"] = reason
                breakdown_key = f"EXCLUDED_{match_res.match_status.value}"
                exclusion_breakdown[breakdown_key] = exclusion_breakdown.get(breakdown_key, 0) + 1
                records_log.append(record_entry)
                continue

            # Signal is matched to a specific candidate
            matched_toi_id = match_res.matched_toi_id
            matched_candidate = next(
                (c for c in target.candidates if c.toi_id == matched_toi_id),
                None,
            )

            if matched_candidate is None:
                excluded_count += 1
                record_entry["exclusion_reason"] = f"Candidate metadata for TOI-{matched_toi_id} missing."
                records_log.append(record_entry)
                continue

            # Populate stellar properties if available from catalog
            if best_cand.stellar_radius_solar is None and matched_candidate.stellar_radius is not None:
                best_cand.stellar_radius_solar = matched_candidate.stellar_radius
            if best_cand.stellar_teff_k is None and matched_candidate.stellar_teff is not None:
                best_cand.stellar_teff_k = matched_candidate.stellar_teff

            # Extract Canonical Feature Vector (Schema 2.0)
            feat_vector = build_feature_vector(best_cand)

            if matched_candidate.supervised_label is None:
                # Ambiguous candidate (PC, APC) -> Excluded from supervised training
                excluded_count += 1
                record_entry["exclusion_reason"] = (
                    f"Candidate TOI-{matched_toi_id} has ambiguous disposition '{matched_candidate.disposition}'. "
                    f"Excluded from supervised training by default."
                )
                exclusion_breakdown["EXCLUDED_AMBIGUOUS_DISPOSITION"] = (
                    exclusion_breakdown.get("EXCLUDED_AMBIGUOUS_DISPOSITION", 0) + 1
                )
                records_log.append(record_entry)
                continue

            # Approved Supervised Sample
            supervised_label = matched_candidate.supervised_label
            record_entry["is_supervised"] = True
            record_entry["supervised_label"] = supervised_label
            record_entry["matched_toi_id"] = matched_toi_id

            if supervised_label == 1:
                pos_count += 1
            else:
                neg_count += 1
            supervised_count += 1

            row = {
                "target_id": tic_id,
                "host_star_id": target.host_star_id or tic_id,
                "toi_id": matched_toi_id,
                "mission": lc.mission.value,
                "sector": lc.sector,
                "label": supervised_label,
                "match_status": match_res.match_status.value,
                "match_method": match_res.match_method.value,
                "period_rel_err": match_res.period_relative_error,
                "epoch_phase_offset": match_res.epoch_phase_offset,
            }
            # Append exact 13 canonical features
            for col in CANONICAL_FEATURES:
                row[col] = feat_vector.get(col, np.nan)

            feature_rows.append(row)
            records_log.append(record_entry)

        features_df = pd.DataFrame(feature_rows)

        # 8. Missingness Analysis across Canonical Features
        feature_missingness: Dict[str, float] = {}
        for col in CANONICAL_FEATURES:
            if col in features_df.columns:
                feature_missingness[col] = float(features_df[col].isna().mean())
            else:
                feature_missingness[col] = 1.0

        # Multi-candidate host star analysis
        host_counts = features_df["host_star_id"].value_counts().to_dict() if not features_df.empty else {}
        multi_candidate_hosts = {h: c for h, c in host_counts.items() if c > 1}

        # 9. Build Comprehensive Manifest
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        parquet_path = output_dir / "features.parquet"
        csv_path = output_dir / "features.csv"
        manifest_path = output_dir / "manifest.json"

        # Save feature tables (CSV is primary standard; Parquet generated when pyarrow/fastparquet available)
        features_df.to_csv(csv_path, index=False)
        has_parquet = False
        try:
            features_df.to_parquet(parquet_path, index=False)
            has_parquet = True
        except (ImportError, ValueError) as exc:
            logger.info(f"Parquet engine not available ({exc}); continuing with CSV.")

        checksums: Dict[str, str] = {
            "features_csv_sha256": compute_file_sha256(csv_path),
        }
        if has_parquet and parquet_path.exists():
            checksums["features_parquet_sha256"] = compute_file_sha256(parquet_path)

        manifest = {
            "manifest_version": "2.0",
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "canonical_features": CANONICAL_FEATURES,
            "feature_metadata": FEATURE_METADATA,
            "configuration": {
                "output_dir": str(output_dir.resolve()),
                "period_tolerance": self.config.period_tolerance,
                "max_phase_offset": self.config.max_phase_offset,
                "min_period": self.config.min_period,
                "max_period": self.config.max_period,
            },
            "dataset_summary": {
                "total_targets_considered": len(targets),
                "light_curves_retrieved": retrieved_count,
                "light_curves_failed": failed_count,
                "total_signals_detected": detected_signals_count,
                "supervised_samples_approved": supervised_count,
                "positive_samples": pos_count,
                "negative_samples": neg_count,
                "unmatched_signals": unmatched_count,
                "excluded_samples": excluded_count,
                "exclusion_breakdown": exclusion_breakdown,
                "class_balance_positive_ratio": (pos_count / supervised_count) if supervised_count > 0 else 0.0,
                "unique_host_stars": len(host_counts),
                "multi_candidate_hosts": len(multi_candidate_hosts),
            },
            "feature_missingness": feature_missingness,
            "checksums": checksums,
            "records": records_log,
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        audit_summary = {
            "output_dir": str(output_dir.resolve()),
            "parquet_path": str(parquet_path.resolve()) if has_parquet else None,
            "csv_path": str(csv_path.resolve()),
            "manifest_path": str(manifest_path.resolve()),
            "total_considered": len(targets),
            "retrieved_count": retrieved_count,
            "failed_count": failed_count,
            "supervised_count": supervised_count,
            "positive_count": pos_count,
            "negative_count": neg_count,
            "excluded_count": excluded_count,
            "feature_missingness": feature_missingness,
            "multi_candidate_hosts": multi_candidate_hosts,
        }

        return features_df, manifest, audit_summary


