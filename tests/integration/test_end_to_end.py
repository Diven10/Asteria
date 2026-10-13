import os
import pytest
import numpy as np
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app

def generate_synthetic_transit_light_curve():
    """Generates a synthetic light curve with a clear transit signal."""
    # 20 days of data, 30 min cadence
    time = np.linspace(0, 20, 20 * 48)
    flux = np.ones_like(time)
    
    # Add a transit: period = 5.0 days, epoch = 2.0, duration = 0.1 days, depth = 0.02
    period = 5.0
    epoch = 2.0
    duration = 0.1
    depth = 0.02
    
    # Phase fold
    phase = (time - epoch + 0.5 * period) % period - 0.5 * period
    transit_mask = np.abs(phase) < (duration / 2.0)
    flux[transit_mask] -= depth
    
    # Add some gaussian noise (SNR ~ 4-5) so the transit isn't removed as an outlier by sigma-clipping
    noise = np.random.normal(0, 0.005, len(time))
    flux += noise
    
    return time.tolist(), flux.tolist(), (np.ones_like(time) * 0.005).tolist()


def test_complete_asteria_pipeline():
    """Tests the full end-to-end ASTERIA pipeline through the API."""
    
    # Inject a mock catalog file so we test TIC characterization
    mock_catalog_path = "tests/fixtures/mock_tic.csv"
    os.environ["ASTERIA_CATALOG_PATH"] = mock_catalog_path
    
    # Ensure the directory exists (might not be if this is a fresh env)
    os.makedirs("tests/fixtures", exist_ok=True)
    with open(mock_catalog_path, "w") as f:
        f.write("TICID,ra,dec,rad,mass,teff,priority,d\n")
        f.write("123456,1.0,1.0,1.0,1.0,5778,0.9,10.0\n")
        
    client = TestClient(app)
    
    time, flux, flux_err = generate_synthetic_transit_light_curve()
    
    payload = {
        "light_curve": {
            "target_id": "123456",
            "mission": "PLATO_SYNTHETIC",
            "time": time,
            "flux": flux,
            "flux_error": flux_err
        },
        "min_period": 3.0,
        "max_period": 8.0,
        "generate_pdf": True
    }
    
    # Request the full analysis
    response = client.post("/pipeline/analyze", json=payload)
    
    assert response.status_code == 200
    results = response.json()
    
    # There should be at least one candidate found
    assert len(results) > 0
    best_candidate = results[0]
    
    # Verify outputs
    assert best_candidate["target_id"] == "123456"
    assert abs(best_candidate["period_days"] - 5.0) < 0.1  # Recovered period close to 5.0
    assert "planet_probability" in best_candidate
    assert "is_valid_astrophysically" in best_candidate
    
    # Check OPS Ranking breakdown is present
    assert "ops_score" in best_candidate
    assert "ops_breakdown" in best_candidate
    assert "confidence_score" in best_candidate["ops_breakdown"]
    
    # Check planetary properties
    assert "size_class" in best_candidate
    assert "habitable_zone_proxy" in best_candidate
    
    # Check PDF report generation
    assert best_candidate.get("pdf_report_path") is not None
    assert str(best_candidate["pdf_report_path"]).endswith(".pdf")
    assert os.path.exists(best_candidate["pdf_report_path"])
    
    # Clean up
    if os.path.exists(best_candidate["pdf_report_path"]):
        os.remove(best_candidate["pdf_report_path"])
    if os.path.exists(mock_catalog_path):
        os.remove(mock_catalog_path)
