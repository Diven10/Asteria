"""NASA Exoplanet Archive TOI Authoritative Ingestion Layer.

Fetches and normalizes authoritative exoplanet dispositions and transit ephemerides
from the NASA Exoplanet Archive TESS Objects of Interest (TOI) catalog.

Authoritative Label Policy:
- Positive (1): TFOPWG Disposition is "CP" (Confirmed Planet) or "KP" (Known Planet).
- Negative (0): TFOPWG Disposition is "FP" (False Positive) or "FA" (False Alarm).
- Ambiguous / Unresolved (Excluded): "PC" (Planet Candidate), "APC", or empty.
  These are excluded from supervised training by default.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests

from app.contracts.models import Mission
from app.ml.dataset_builder import AuthoritativeTarget
from app.ml.signal_matcher import CatalogEphemeris

logger = logging.getLogger(__name__)


@dataclass
class AuthoritativeTOICandidate:
    """Represents a single candidate-level TOI record with orbital ephemeris."""

    toi_id: str
    tic_id: str
    disposition: str
    supervised_label: Optional[int]
    period_days: Optional[float]
    epoch_bjd: Optional[float]
    duration_hours: Optional[float]
    depth_ppm: Optional[float]
    stellar_radius: Optional[float] = None
    stellar_teff: Optional[float] = None
    sectors: List[int] = field(default_factory=list)
    retrieval_timestamp: Optional[str] = field(default=None, compare=False)
    provenance: str = "NASA_Exoplanet_Archive_TOI"

    def to_catalog_ephemeris(self) -> Optional[CatalogEphemeris]:
        if self.period_days is None or self.epoch_bjd is None:
            return None
        return CatalogEphemeris(
            toi_id=self.toi_id,
            tic_id=self.tic_id,
            period_days=self.period_days,
            epoch_bjd=self.epoch_bjd,
            duration_hours=self.duration_hours,
            depth_ppm=self.depth_ppm,
            disposition=self.disposition,
        )


@dataclass
class AuthoritativeDatasetResult:
    """Result of processing authoritative TOI data."""

    targets: List[AuthoritativeTarget]
    metadata: Dict[str, Any]
    rejected_count: int
    rejected_reasons: Dict[str, int]


class TOIAuthoritativeSource:
    """Ingests authoritative TESS Objects of Interest (TOI) from NASA Exoplanet Archive."""

    SOURCE_NAME = "NASA_Exoplanet_Archive_TOI"
    ENDPOINT = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"

    # Strict label mappings
    POSITIVE_DISPOSITIONS = frozenset({"CP", "KP"})
    NEGATIVE_DISPOSITIONS = frozenset({"FP", "FA"})
    AMBIGUOUS_DISPOSITIONS = frozenset({"PC", "APC", ""})

    def __init__(self, reject_mixed: bool = True, timeout: int = 30):
        self.reject_mixed = reject_mixed
        self.timeout = timeout

    def _fetch_raw_data(self, where_clause: Optional[str] = None, limit: Optional[int] = None) -> pd.DataFrame:
        """Fetches raw TOI table columns via TAP sync API with CSV format."""
        limit_str = f"top {limit} " if limit else ""
        where_str = f" where {where_clause}" if where_clause else ""
        query = (
            f"select {limit_str}tid, toi, tfopwg_disp, "
            f"pl_orbper, pl_tranmid, pl_trandurh, pl_trandep, sectors, st_rad, st_teff "
            f"from toi{where_str}"
        )
        params = {"query": query, "format": "csv"}

        response = requests.get(self.ENDPOINT, params=params, timeout=self.timeout)
        response.raise_for_status()

        df = pd.read_csv(io.StringIO(response.text))
        if "tic_id" not in df.columns and "tid" in df.columns:
            df["tic_id"] = df["tid"]
        return df


    def _parse_sectors(self, sectors_val: Any) -> List[int]:
        if pd.isna(sectors_val) or not sectors_val:
            return []
        sectors_str = str(sectors_val)
        out = []
        for s in sectors_str.split(","):
            s_clean = s.strip()
            try:
                out.append(int(s_clean))
            except (ValueError, TypeError):
                continue
        return sorted(list(set(out)))

    def process(
        self,
        raw_df: Optional[pd.DataFrame] = None,
        include_ambiguous: bool = False,
    ) -> AuthoritativeDatasetResult:

        """Processes raw DataFrame into AuthoritativeTarget records with ephemerides."""
        if raw_df is None:
            raw_df = self._fetch_raw_data()

        retrieval_timestamp = datetime.now(timezone.utc).isoformat()

        if raw_df.empty:
            raise ValueError("Provided dataset is empty.")

        # Incompatible catalog check (reject CTL)
        cols_lower = [str(c).lower() for c in raw_df.columns]
        if "cooldwarfs" in str(raw_df.values)[:200].lower() or "planetcandidate" in cols_lower:
            raise ValueError(
                "Provided dataset appears to be the TESS Candidate Target List (CTL). "
                "CTL is a target-selection star catalog, not an exoplanet disposition archive."
            )

        # Standardize column names
        if "tic_id" not in raw_df.columns and "tid" in raw_df.columns:
            raw_df["tic_id"] = raw_df["tid"]

        required_cols = {"tic_id", "tfopwg_disp"}
        missing = required_cols - set(raw_df.columns)
        if missing:
            raise ValueError(f"Missing required columns in TOI table: {missing}")

        targets_out: List[AuthoritativeTarget] = []
        rejected_reasons = {
            "missing_tic": 0,
            "unresolved_ambiguous": 0,
            "mixed_dispositions": 0,
        }

        grouped = raw_df.groupby("tic_id")

        for tic_id, group in grouped:
            if pd.isna(tic_id) or not str(tic_id).strip():
                rejected_reasons["missing_tic"] += 1
                continue

            tic_id_str = str(int(float(tic_id)))

            # Parse candidates for this target
            cand_objects: List[AuthoritativeTOICandidate] = []
            for _, row in group.iterrows():
                disp = str(row.get("tfopwg_disp", "")).strip().upper()
                toi_val = str(row.get("toi", "")).strip()

                if disp in self.POSITIVE_DISPOSITIONS:
                    sub_label = 1
                elif disp in self.NEGATIVE_DISPOSITIONS:
                    sub_label = 0
                else:
                    sub_label = None

                p_val = float(row["pl_orbper"]) if pd.notna(row.get("pl_orbper")) else None
                e_val = float(row["pl_tranmid"]) if pd.notna(row.get("pl_tranmid")) else None
                d_val = float(row["pl_trandurh"]) if pd.notna(row.get("pl_trandurh")) else None
                dep_val = float(row["pl_trandep"]) if pd.notna(row.get("pl_trandep")) else None
                rad_val = float(row["st_rad"]) if pd.notna(row.get("st_rad")) else None
                teff_val = float(row["st_teff"]) if pd.notna(row.get("st_teff")) else None
                secs = self._parse_sectors(row.get("sectors"))

                cand_objects.append(
                    AuthoritativeTOICandidate(
                        toi_id=toi_val,
                        tic_id=tic_id_str,
                        disposition=disp,
                        supervised_label=sub_label,
                        period_days=p_val,
                        epoch_bjd=e_val,
                        duration_hours=d_val,
                        depth_ppm=dep_val,
                        stellar_radius=rad_val,
                        stellar_teff=teff_val,
                        sectors=secs,
                        retrieval_timestamp=retrieval_timestamp,
                        provenance=self.SOURCE_NAME,
                    )
                )

            dispositions = set(c.disposition for c in cand_objects)

            has_positive = bool(dispositions.intersection(self.POSITIVE_DISPOSITIONS))
            has_negative = bool(dispositions.intersection(self.NEGATIVE_DISPOSITIONS))
            has_ambiguous = bool(dispositions.intersection(self.AMBIGUOUS_DISPOSITIONS)) or len(dispositions) == 0

            # Target-level disposition resolution
            if has_ambiguous:
                rejected_reasons["unresolved_ambiguous"] += 1
                if not include_ambiguous:
                    continue
                target_label = None
            elif has_positive and has_negative and self.reject_mixed:
                rejected_reasons["mixed_dispositions"] += 1
                if not include_ambiguous:
                    continue
                target_label = None
            elif has_positive:
                target_label = 1
            elif has_negative:
                target_label = 0
            else:
                rejected_reasons["unresolved_ambiguous"] += 1
                if not include_ambiguous:
                    continue
                target_label = None

            # Default sector selection (prefer lowest available sector)
            all_sectors = []
            for c in cand_objects:
                all_sectors.extend(c.sectors)
            selected_sector = min(all_sectors) if all_sectors else None

            targets_out.append(
                AuthoritativeTarget(
                    target_id=tic_id_str,
                    mission=Mission.TESS,
                    authoritative_label=target_label,
                    host_star_id=tic_id_str,
                    sector=selected_sector,
                    provenance=self.SOURCE_NAME,
                    candidates=cand_objects,
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
                "negative": sum(1 for t in targets_out if t.authoritative_label == 0),
                "ambiguous_excluded": sum(1 for t in targets_out if t.authoritative_label is None),
            },
        }

        return AuthoritativeDatasetResult(
            targets=targets_out,
            metadata=metadata,
            rejected_count=sum(rejected_reasons.values()),
            rejected_reasons=rejected_reasons,
        )

    def fetch_pilot_targets(
        self,
        n_positive: int = 5,
        n_negative: int = 5,
        n_ambiguous: int = 2,
    ) -> List[AuthoritativeTarget]:
        """Fetches a balanced, verified pilot sample across authoritative dispositions."""
        limit_count = max(200, (n_positive + n_negative + n_ambiguous) * 20)
        query = (
            f"select top {limit_count} tid, toi, tfopwg_disp, "
            f"pl_orbper, pl_tranmid, pl_trandurh, pl_trandep, sectors, st_rad, st_teff "
            f"from toi where tfopwg_disp in ('CP', 'KP', 'FP', 'FA', 'PC')"
        )
        params = {"query": query, "format": "csv"}
        resp = requests.get(self.ENDPOINT, params=params, timeout=self.timeout)
        resp.raise_for_status()
        raw_df = pd.read_csv(io.StringIO(resp.text))
        if "tic_id" not in raw_df.columns and "tid" in raw_df.columns:
            raw_df["tic_id"] = raw_df["tid"]

        pos_df = raw_df[raw_df["tfopwg_disp"].isin(list(self.POSITIVE_DISPOSITIONS))]
        neg_df = raw_df[raw_df["tfopwg_disp"].isin(list(self.NEGATIVE_DISPOSITIONS))]
        amb_df = raw_df[raw_df["tfopwg_disp"].isin(list(self.AMBIGUOUS_DISPOSITIONS))]

        pos_tics = list(pos_df["tid"].dropna().drop_duplicates().head(n_positive))
        neg_tics = list(neg_df["tid"].dropna().drop_duplicates().head(n_negative))
        amb_tics = list(amb_df["tid"].dropna().drop_duplicates().head(n_ambiguous))

        selected_tics = set(pos_tics + neg_tics + amb_tics)
        subset_df = raw_df[raw_df["tid"].isin(selected_tics)].copy()

        result = self.process(subset_df, include_ambiguous=True)
        return result.targets
