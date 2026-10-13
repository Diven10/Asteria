from fastapi.testclient import TestClient
import numpy as np
from uuid import uuid4

from app.main import app

client = TestClient(app)

def test_dashboard_workflow():
    # 1. Preprocess
    time = np.linspace(0, 10, 100).tolist()
    flux = (np.ones(100) + np.random.normal(0, 0.001, 100)).tolist()
    lc_payload = {
        "target_id": "TIC 12345",
        "mission": "TESS",
        "time": time,
        "flux": flux,
        "flux_error": [0.01] * 100
    }
    
    res = client.post("/dashboard/preprocess", json=lc_payload)
    assert res.status_code == 200
    processed_lc = res.json()
    assert processed_lc["target_id"] == "TIC 12345"
    
    # 2. Detect
    detect_payload = {
        "light_curve": processed_lc,
        "min_period": 1.0,
        "max_period": 5.0
    }
    res = client.post("/dashboard/detect", json=detect_payload)
    assert res.status_code == 200
    candidates = res.json()
    assert isinstance(candidates, list)
    
    # We might not find any candidates in pure noise, so let's mock a detection candidate
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
    
    # 3. Classify
    res = client.post("/dashboard/classify", json=cand_payload)
    assert res.status_code == 200
    classified = res.json()
    assert "planet_probability" in classified
    assert "prediction" in classified
    
    # 4. Properties
    res = client.post("/dashboard/properties", json=cand_payload)
    assert res.status_code == 200
    props = res.json()
    assert "radius_earth" in props
    
    # 5. Validate
    res = client.post("/dashboard/validate", json=classified)
    assert res.status_code == 200
    validation = res.json()
    assert "is_valid_astrophysically" in validation
    
    # 6. Explain
    res = client.post("/dashboard/explain", json=classified)
    assert res.status_code == 200
    explanation = res.json()
    assert "is_valid" in explanation
    
    # 7. OPS
    ops_payload = {
        "classified": classified,
        "props": props,
        "validation": validation
    }
    res = client.post("/dashboard/score", json=ops_payload)
    assert res.status_code == 200
    ops = res.json()
    assert "total_score" in ops
    assert "breakdown" in ops
    
    # 8. Report
    report_payload = {
        "classified": classified,
        "props": props,
        "ops_result": ops,
        "validation": validation,
        "shap_explanation": explanation
    }
    res = client.post("/dashboard/report", json=report_payload)
    assert res.status_code == 200
    report = res.json()
    assert report["status"] == "queued"
    assert "ASTERIA_Report_" in report["report_path"]

def test_dashboard_ingest_unsupported():
    res = client.post("/dashboard/ingest", json={"target": "foo", "mission": "UNKNOWN"})
    assert res.status_code == 400
    assert "Unsupported mission" in res.json()["detail"]

def test_export_lightcurve_csv():
    import numpy as np
    time = np.linspace(0, 10, 10).tolist()
    flux = np.ones(10).tolist()
    lc_payload = {
        "target_id": "TIC 12345",
        "mission": "TESS",
        "time": time,
        "flux": flux,
        "flux_error": [0.01] * 10
    }
    res = client.post("/dashboard/export/lightcurve/csv", json=lc_payload)
    assert res.status_code == 200
    assert res.headers["content-type"] == "text/csv; charset=utf-8"
    csv_text = res.text
    assert "time,flux,flux_error" in csv_text

def test_download_sample_fits():
    res = client.get("/dashboard/sample-fits")
    assert res.status_code == 200
    assert len(res.content) > 1000

def test_upload_sample_fits_file():
    with open("sample_data/tess_pi_mensae_c_lc.fits", "rb") as f:
        res = client.post(
            "/dashboard/upload",
            files={"file": ("tess_pi_mensae_c_lc.fits", f, "application/fits")}
        )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["target_id"] == "261136679"
    assert len(data["time"]) > 0
