import requests
from fastapi.testclient import TestClient
from app.main import app
import numpy as np
from uuid import uuid4

client = TestClient(app)
cand_payload = {
    "candidate_id": str(uuid4()),
    "light_curve_id": str(uuid4()),
    "target_id": "TIC 12345",
    "mission": "TESS",
    "period_days": 2.5,
    "epoch_btjd": 1.0,
    "duration_hours": 1.0,
    "depth": 0.01,
    "bls_power": 50.0,
    "snr": 10.0,
    "transit_count": 5,
    "stellar_radius_solar": 1.0,
    "stellar_mass_solar": 1.0,
    "stellar_teff_k": 5778
}
res = client.post("/dashboard/classify", json=cand_payload)
classified = res.json()
print("CLASSIFIED:", classified)
res = client.post("/dashboard/validate", json=classified)
print("VALIDATE STATUS:", res.status_code)
print("VALIDATE RESPONSE:", res.json())
