import pandas as pd
import json
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, List, Callable, Dict, Any, Tuple
import logging

from app.contracts.models import LightCurve, Mission, DetectionCandidate
from app.preprocessing.pipeline import preprocess_light_curve
from app.detection.bls import BLSDetector
from app.features.engineering import build_feature_vector, FEATURE_SCHEMA_VERSION

logger = logging.getLogger(__name__)

@dataclass
class AuthoritativeTarget:
    """
    Strict contract for incoming authoritative targets.
    Prevents inventing labels or fabricating data.
    """
    target_id: str
    mission: Mission
    authoritative_label: int  # e.g., 1 for planet, 0 for false positive
    host_star_id: str
    sector: Optional[int] = None
    provenance: str = "Unknown"

@dataclass
class BuilderConfig:
    """Configures the DatasetBuilder execution."""
    fail_fast: bool = False
    min_period: float = 1.0
    max_period: float = 20.0

class IngestionInterface:
    """
    Abstract interface for ingestion.
    Allows injecting mocked services during dataset creation.
    """
    def ingest(self, target: AuthoritativeTarget) -> LightCurve:
        raise NotImplementedError

def select_highest_bls_power(candidates: List[DetectionCandidate]) -> Optional[DetectionCandidate]:
    """
    Default deterministic strategy: select the candidate with the highest BLS power.
    This is an engineering dataset-construction policy, NOT an astronomical truth claim.
    """
    if not candidates:
        return None
    return max(candidates, key=lambda c: c.bls_power)

class DatasetBuilder:
    """
    Orchestrates the conversion of authoritative astronomical targets into
    a reproducible feature dataset (X, y, groups) for ML training.
    """
    def __init__(
        self,
        ingestion_service: IngestionInterface,
        config: Optional[BuilderConfig] = None,
        candidate_selector: Optional[Callable[[List[DetectionCandidate]], Optional[DetectionCandidate]]] = None
    ):
        self.ingestion_service = ingestion_service
        self.config = config or BuilderConfig()
        self.candidate_selector = candidate_selector or select_highest_bls_power
        self.detector = BLSDetector(min_period=self.config.min_period, max_period=self.config.max_period)

    def build(self, targets: List[AuthoritativeTarget]) -> Tuple[pd.DataFrame, Dict[str, Any], List[Dict[str, Any]]]:
        """
        Executes the dataset generation pipeline.
        
        Returns:
            - df: DataFrame containing features (X), labels (y), and groups (host_star_id).
            - metadata: Dictionary describing dataset provenance.
            - failures: List of targets that failed processing.
        """
        rows = []
        failures = []

        for target in targets:
            # 1. Strict Input Validation
            if target.authoritative_label is None:
                err = f"Missing authoritative label for target {target.target_id}."
                failures.append({"target_id": target.target_id, "stage": "validation", "error": err})
                if self.config.fail_fast:
                    raise ValueError(err)
                continue

            if not target.host_star_id:
                err = f"Missing host_star_id for target {target.target_id}."
                failures.append({"target_id": target.target_id, "stage": "validation", "error": err})
                if self.config.fail_fast:
                    raise ValueError(err)
                continue

            try:
                # 2. Ingest
                lc = self.ingestion_service.ingest(target)

                # 3. Preprocess
                processed_lc = preprocess_light_curve(lc)

                # 4. Detect
                candidates = self.detector.detect(processed_lc)

                # 5. Select Candidate
                best_cand = self.candidate_selector(candidates)
                if not best_cand:
                    err = "No BLS candidates detected."
                    failures.append({"target_id": target.target_id, "stage": "detection", "error": err})
                    if self.config.fail_fast:
                        raise ValueError(err)
                    continue

                # 6. Extract Features
                features = build_feature_vector(best_cand)

                # 7. Construct Row
                row = {
                    "target_id": target.target_id,
                    "mission": target.mission.value if isinstance(target.mission, Mission) else target.mission,
                    "sector": target.sector,
                    "host_star_id": target.host_star_id,
                    "authoritative_label": target.authoritative_label,
                    "provenance": target.provenance
                }
                row.update(features)
                rows.append(row)

            except Exception as e:
                err = str(e)
                failures.append({"target_id": target.target_id, "stage": "execution", "error": err})
                if self.config.fail_fast:
                    raise

        df = pd.DataFrame(rows)

        metadata = {
            "creation_timestamp": datetime.now(timezone.utc).isoformat(),
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "target_count": len(targets),
            "successful_count": len(rows),
            "failed_count": len(failures)
        }

        return df, metadata, failures

    def save_csv(self, df: pd.DataFrame, metadata: Dict[str, Any], filepath: str, metadata_filepath: str):
        """Persists the constructed dataset and its provenance metadata."""
        df.to_csv(filepath, index=False)
        with open(metadata_filepath, "w") as f:
            json.dump(metadata, f, indent=2)
