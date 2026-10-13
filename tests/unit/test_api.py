from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_pipeline_analyze() -> None:
    # A simple mock lightcurve
    import numpy as np
    from uuid import uuid4
    time = np.linspace(0, 10, 100).tolist()
    flux = (np.ones(100) + np.random.normal(0, 0.001, 100)).tolist()
    
    payload = {
        "light_curve": {
            "target_id": "TIC 123",
            "mission": "TESS",
            "time": time,
            "flux": flux,
            "flux_error": [0.01] * 100
        },
        "min_period": 1.0,
        "max_period": 5.0,
        "generate_pdf": True
    }
    
    response = client.post("/pipeline/analyze", json=payload)
    if response.status_code != 200:
        print(response.json())
    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)
    if len(results) > 0:
        res = results[0]
        assert "target_id" in res
        assert "planet_probability" in res
        if res.get("pdf_report_path"):
            assert str(res["pdf_report_path"]).endswith(".pdf")

