import pandas as pd
import requests
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.contracts.models import Mission
from app.ml.dataset_builder import AuthoritativeTarget

logger = logging.getLogger(__name__)

@dataclass
class AuthoritativeDatasetResult:
    targets: List[AuthoritativeTarget]
    metadata: Dict[str, Any]
    rejected_count: int
    rejected_reasons: Dict[str, int]

class TOIAuthoritativeSource:
    """
    NASA Exoplanet Archive - TESS Objects of Interest (TOI) Source.
    
    Label Policy:
    - Positive (1): TFOPWG Disposition is "CP" (Confirmed Planet) or "KP" (Known Planet).
    - Negative (0): TFOPWG Disposition is "FP" (False Positive) or "FA" (False Alarm).
    - Ambiguous (Reject): "PC" (Planet Candidate), "APC", or empty.
    
    Duplicates (same TIC ID, multiple TOIs):
    - If a TIC has ANY ambiguous disposition (e.g., PC), it is rejected.
    - If a TIC has ONLY FP/FA, it is Negative.
    - If a TIC has CP/KP, it is Positive (even if it also has an FP, though we optionally reject mixed for safety).
      For maximum safety, if a TIC has both Positive and Negative, we reject it.
    """
    
    SOURCE_NAME = "NASA_Exoplanet_Archive_TOI"
    ENDPOINT = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
    
    def __init__(self, reject_mixed: bool = True):
        self.reject_mixed = reject_mixed
        
    def _fetch_raw_data(self) -> pd.DataFrame:
        """Fetches the raw TOI table from the NASA Exoplanet Archive."""
        query = "select tic_id, toi, tfopwg_disp, sectors from toi"
        params = {
            "query": query,
            "format": "json"
        }
        
        response = requests.get(self.ENDPOINT, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        return pd.DataFrame(data)

    def process(self, raw_df: Optional[pd.DataFrame] = None) -> AuthoritativeDatasetResult:
        """
        Processes a raw DataFrame (or fetches one) into AuthoritativeTargets.
        """
        if raw_df is None:
            raw_df = self._fetch_raw_data()
            
        retrieval_timestamp = datetime.now(timezone.utc).isoformat()
        
        if raw_df.empty:
            raise ValueError("Provided dataset is empty.")
            
        # Ensure required columns
        required_cols = {"tic_id", "tfopwg_disp"}
        missing = required_cols - set(raw_df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        targets_out = []
        rejected_reasons = {
            "missing_tic": 0,
            "unresolved_ambiguous": 0,
            "mixed_dispositions": 0
        }
        
        # Group by TIC ID to handle multiple TOIs per light curve
        grouped = raw_df.groupby("tic_id")
        
        for tic_id, group in grouped:
            if pd.isna(tic_id) or not str(tic_id).strip():
                rejected_reasons["missing_tic"] += 1
                continue
                
            tic_id_str = str(int(tic_id)) if isinstance(tic_id, float) else str(tic_id)
            dispositions = set(group["tfopwg_disp"].dropna().str.strip().str.upper())
            
            # Map dispositions to classes
            has_positive = bool(dispositions.intersection({"CP", "KP"}))
            has_negative = bool(dispositions.intersection({"FP", "FA"}))
            has_ambiguous = bool(dispositions.intersection({"PC", "APC", ""})) or len(dispositions) == 0
            
            if has_ambiguous:
                rejected_reasons["unresolved_ambiguous"] += 1
                continue
                
            if has_positive and has_negative and self.reject_mixed:
                rejected_reasons["mixed_dispositions"] += 1
                continue
                
            if has_positive:
                label = 1
            elif has_negative:
                label = 0
            else:
                rejected_reasons["unresolved_ambiguous"] += 1
                continue
                
            # Attempt to extract sector (just grab the first one if multiple exist)
            sectors_val = group.get("sectors")
            sector = None
            if sectors_val is not None:
                first_valid = sectors_val.dropna().astype(str).str.split(",").explode().str.strip().first_valid_index()
                if first_valid is not None:
                    try:
                        val = str(sectors_val.loc[first_valid]).split(",")[0].strip()
                        sector = int(val)
                    except (ValueError, TypeError):
                        pass

            targets_out.append(
                AuthoritativeTarget(
                    target_id=tic_id_str,
                    mission=Mission.TESS,
                    authoritative_label=label,
                    host_star_id=tic_id_str,
                    sector=sector,
                    provenance=self.SOURCE_NAME
                )
            )
            
        metadata = {
            "source_name": self.SOURCE_NAME,
            "query_table": "toi",
            "retrieval_timestamp": retrieval_timestamp,
            "total_raw_rows": len(raw_df),
            "total_unique_tics": len(grouped),
            "accepted_targets": len(targets_out),
            "label_distribution": {
                "positive": sum(1 for t in targets_out if t.authoritative_label == 1),
                "negative": sum(1 for t in targets_out if t.authoritative_label == 0)
            }
        }
        
        return AuthoritativeDatasetResult(
            targets=targets_out,
            metadata=metadata,
            rejected_count=sum(rejected_reasons.values()),
            rejected_reasons=rejected_reasons
        )
