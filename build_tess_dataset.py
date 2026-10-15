"""ASTERIA Dataset Generation CLI.

Executes the real TESS dataset pipeline:
- Ingests authoritative TOI dispositions and orbital ephemerides.
- Retrieves real calibrated TESS light curves.
- Detects transit signals with BLS.
- Performs candidate-level ephemeris matching.
- Extracts canonical Schema 2.0 feature vectors.
- Persists features.csv and manifest.json.
- Prints the comprehensive audit report.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from app.ml.tess_dataset_pipeline import DatasetPipelineConfig, TESSDatasetPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_tess_dataset")


def main():
    parser = argparse.ArgumentParser(description="ASTERIA Real Labelled TESS Dataset Generation")
    parser.add_argument("--output-dir", type=str, default="data/labelled_dataset", help="Output directory for feature table and manifest")
    parser.add_argument("--pilot-positive", type=int, default=5, help="Number of positive (CP/KP) targets to retrieve")
    parser.add_argument("--pilot-negative", type=int, default=5, help="Number of negative (FP/FA) targets to retrieve")
    parser.add_argument("--pilot-ambiguous", type=int, default=2, help="Number of ambiguous (PC/APC) targets to retrieve")
    parser.add_argument("--specific-tics", type=str, default=None, help="Comma-separated list of specific TIC IDs to process")
    parser.add_argument("--period-tolerance", type=float, default=0.03, help="Fractional period matching tolerance (default 0.03)")
    parser.add_argument("--max-phase-offset", type=float, default=0.05, help="Maximum folded phase tolerance (default 0.05)")
    args = parser.parse_args()

    specific_list = [t.strip() for t in args.specific_tics.split(",") if t.strip()] if args.specific_tics else None

    config = DatasetPipelineConfig(
        output_dir=args.output_dir,
        pilot_positive=args.pilot_positive,
        pilot_negative=args.pilot_negative,
        pilot_ambiguous=args.pilot_ambiguous,
        specific_tic_ids=specific_list,
        period_tolerance=args.period_tolerance,
        max_phase_offset=args.max_phase_offset,
    )

    logger.info("Initializing ASTERIA Real TESS Dataset Pipeline...")
    pipeline = TESSDatasetPipeline(config=config)

    logger.info("Running pipeline execution...")
    features_df, manifest, audit = pipeline.run_pipeline()

    print("\n" + "=" * 70)
    print("ASTERIA REAL LABELLED TESS DATASET — GENERATION AUDIT REPORT")
    print("=" * 70)
    summary = manifest["dataset_summary"]
    print(f"Total Targets Considered:          {summary['total_targets_considered']}")
    print(f"Light Curves Retrieved:            {summary['light_curves_retrieved']}")
    print(f"Light Curves Failed:               {summary['light_curves_failed']}")
    print(f"Total Transit Signals Detected:    {summary['total_signals_detected']}")
    print(f"Supervised Samples Approved:       {summary['supervised_samples_approved']}")
    print(f"  - Positive Samples (CP/KP):      {summary['positive_samples']}")
    print(f"  - Negative Samples (FP/FA):      {summary['negative_samples']}")
    print(f"Unmatched BLS Signals:             {summary['unmatched_signals']}")
    print(f"Excluded Samples:                  {summary['excluded_samples']}")
    print(f"Unique Host Stars:                 {summary['unique_host_stars']}")
    print(f"Multi-Candidate Host Stars:        {summary['multi_candidate_hosts']}")
    print("\nExclusion Breakdown:")
    for k, v in summary["exclusion_breakdown"].items():
        print(f"  - {k}: {v}")

    print("\nCanonical Feature Missingness (Schema 2.0):")
    for feat, miss in manifest["feature_missingness"].items():
        print(f"  - {feat:28s}: {miss * 100:.1f}%")

    print("\nGenerated Dataset Artifacts:")
    print(f"  - Features CSV:                  {audit['csv_path']}")
    if audit.get("parquet_path"):
        print(f"  - Features Parquet:              {audit['parquet_path']}")
    print(f"  - Provenance Manifest:           {audit['manifest_path']}")
    print(f"  - CSV Checksum (SHA-256):        {manifest['checksums']['features_csv_sha256']}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
