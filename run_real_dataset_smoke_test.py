import sys
import logging
from app.contracts.models import Mission
from app.ml.dataset_builder import AuthoritativeTarget, DatasetBuilder
from app.ml.tess_dataset import TESSAcquisitionLayer
from app.ingestion.service import IngestionService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_smoke_test():
    target = AuthoritativeTarget(
        target_id="261136679",  # Pi Mensae
        mission=Mission.TESS,
        authoritative_label=1,  # CP/KP
        host_star_id="261136679",
        sector=1,
        provenance="NASA_Exoplanet_Archive_TOI"
    )
    
    logger.info("Initializing Acquisition Layer...")
    service = IngestionService()
    layer = TESSAcquisitionLayer(service)
    
    logger.info(f"Acquiring {target.target_id}...")
    lc = layer.ingest(target)
    logger.info(f"Acquisition successful. Samples: {len(lc.time)}")
    
    logger.info("Initializing DatasetBuilder...")
    builder = DatasetBuilder(ingestion_service=layer)
    
    logger.info("Building dataset row...")
    df, meta, failures = builder.build([target])
    
    if failures:
        logger.error(f"Failures occurred: {failures}")
        sys.exit(1)
        
    logger.info(f"Dataset Built Successfully. Shape: {df.shape}")
    logger.info(f"Features extracted: {list(df.columns)}")
    logger.info(f"Provenance logs: {layer.acquisition_log}")

if __name__ == "__main__":
    run_smoke_test()
