import asyncio
from app.ingestion.service import IngestionService
from app.preprocessing.pipeline import preprocess_light_curve
from app.detection.bls import BLSDetector
from app.ml.classifier import ExoplanetClassifier
from app.contracts.models import LightCurve

service = IngestionService()
print("Ingesting...")
lc = service.download_tess("TIC 261136679", sector=1)
print(f"Ingested {len(lc.time)} points.")

print("Preprocessing...")
preprocessed = preprocess_light_curve(lc)
print(f"Preprocessed {len(preprocessed.time)} points.")

print("Detecting...")
detector = BLSDetector(min_period=1.0, max_period=10.0)
candidates = detector.detect(preprocessed)
print(f"Found {len(candidates)} candidates.")

if candidates:
    best = candidates[0]
    print("Candidate:", best)
    
    print("Classifying...")
    classifier = ExoplanetClassifier()
    classified = classifier.predict(best)
    print("Classified:", classified)
