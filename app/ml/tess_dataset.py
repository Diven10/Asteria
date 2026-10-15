import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.ml.dataset_builder import AuthoritativeTarget, IngestionInterface
from app.contracts.models import LightCurve
from app.ingestion.service import IngestionService

logger = logging.getLogger(__name__)

class TESSAcquisitionLayer(IngestionInterface):
    """
    Acquisition layer mapping AuthoritativeTarget to real TESS light curves.
    Ensures deterministic sector selection, records caching/download provenance,
    and integrates tightly with the existing IngestionService.
    """
    def __init__(self, ingestion_service: IngestionService, download_dir: Optional[str] = None):
        self.ingestion_service = ingestion_service
        self.download_dir = download_dir
        self.acquisition_log: List[Dict[str, Any]] = []

    def _resolve_sector(self, target_id: str, requested_sector: Optional[int] = None) -> Optional[int]:
        """
        Deterministically selects a sector.
        If a sector is provided, it uses it.
        Otherwise, it queries MAST for available sectors and picks the lowest one.
        """
        if requested_sector is not None:
            return requested_sector
            
        import lightkurve as lk
        try:
            # Broad search to find available sectors (prefer SPOC, fallback to any TESS author)
            search_result = lk.search_lightcurve(f"TIC {target_id}", mission="TESS", author="SPOC")
            if len(search_result) == 0:
                search_result = lk.search_lightcurve(f"TIC {target_id}", mission="TESS")
            if len(search_result) == 0:
                return None
            
            # Sequence numbers correspond to TESS sectors in MAST/lightkurve search results
            valid_sectors = []
            if hasattr(search_result, "table") and "sequence_number" in search_result.table.colnames:
                for s in search_result.table["sequence_number"]:
                    try:
                        if s is not None:
                            valid_sectors.append(int(s))
                    except (ValueError, TypeError):
                        continue
            elif hasattr(search_result, "sector"):
                sectors = getattr(search_result, "sector", [])
                valid_sectors = [int(s) for s in sectors if s is not None]

            # Deterministic selection: pick the lowest sector number
            if not valid_sectors:
                return None
                
            return min(valid_sectors)
        except Exception as e:
            raise RuntimeError(f"Sector resolution failed for target {target_id}: {e}") from e

    def ingest(self, target: AuthoritativeTarget) -> LightCurve:
        """
        Executes the acquisition lookup and download.
        Records provenance explicitly on success or failure.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            # 1. Resolve Sector
            selected_sector = self._resolve_sector(target.target_id, target.sector)
            if selected_sector is None:
                raise ValueError("No TESS sectors found or requested sector unavailable.")

            # 2. Acquire via existing infrastructure (caches natively via lightkurve)
            lc = self.ingestion_service.download_tess(
                f"TIC {target.target_id}",
                sector=selected_sector,
                download_dir=self.download_dir
            )
            
            # 3. Record provenance
            cache_path = str(self.download_dir) if self.download_dir else "~/.lightkurve/cache"
            self.acquisition_log.append({
                "tic_id": target.target_id,
                "mission": "TESS",
                "sector": selected_sector,
                "source": "MAST/TESS",
                "retrieval_timestamp": timestamp,
                "local_cache_path": cache_path,
                "acquisition_status": "SUCCESS",
                "error": None
            })
            
            return lc
            
        except Exception as e:
            # 4. Record Failure
            self.acquisition_log.append({
                "tic_id": target.target_id,
                "requested_sector": target.sector,
                "failure_stage": "acquisition",
                "error": str(e),
                "acquisition_status": "FAILED"
            })
            raise
