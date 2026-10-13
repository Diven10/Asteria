import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# just replicate the exact payload that fails
def debug():
    from uuid import uuid4
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
    
    classified = client.post("/dashboard/classify", json=cand_payload).json()
    props = client.post("/dashboard/properties", json=cand_payload).json()
    validation = client.post("/dashboard/validate", json=classified).json()
    explanation = client.post("/dashboard/explain", json=classified).json()
    
    ops_payload = {
        "classified": classified,
        "props": props,
        "validation": validation
    }
    ops = client.post("/dashboard/score", json=ops_payload).json()
    
    report_payload = {
        "classified": classified,
        "props": props,
        "ops_result": ops,
        "validation": validation,
        "shap_explanation": explanation
    }
    res = client.post("/dashboard/report", json=report_payload)
    print(res.status_code)
    print(res.text)

debug()
