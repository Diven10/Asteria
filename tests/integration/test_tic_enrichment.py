import os
import tempfile
import gzip
from fastapi.testclient import TestClient
from app.main import app

def test_tic_v8_enrichment_in_pipeline(monkeypatch):
    """
    Integration test proving the pipeline can perform TIC enrichment
    using the real TIC v8.1 reader interface.
    """
    client = TestClient(app)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock TIC v8.1 CSV file (125 columns)
        tic_path = os.path.join(tmpdir, "mock_tic_v8.csv")
        
        # We only need enough columns to reach the max index used.
        # Max index in field positions is 88 (Priority), so we need 125 columns.
        row = [""] * 125
        row[0] = "99999" # TIC ID
        row[13] = "10.0" # RA
        row[14] = "20.0" # Dec
        row[60] = "12.0" # TESS Mag
        row[64] = "5778" # Teff
        row[66] = "4.44" # logg
        row[68] = "0.0"  # metallicity
        row[70] = "1.0"  # radius
        row[72] = "1.0"  # mass
        row[77] = "1.0"  # luminosity
        row[79] = "10.0" # distance
        row[87] = "1.0"  # priority
        
        with open(tic_path, "w") as f:
            f.write(",".join(row) + "\n")
            
        monkeypatch.setenv("ASTERIA_TIC_PATH", tic_path)
        # Ensure CTL is not used
        monkeypatch.delenv("ASTERIA_CATALOG_PATH", raising=False)
        
        # Create a simple synthetic candidate in the dashboard workflow
        from uuid import uuid4
        import numpy as np
        
        time = np.linspace(0, 10, 100).tolist()
        flux = (np.ones(100) + np.random.normal(0, 0.001, 100)).tolist()
        
        # We need a candidate object for classification that matches our target
        cand_payload = {
            "candidate_id": str(uuid4()),
            "light_curve_id": str(uuid4()),
            "target_id": "99999", # Must match TIC ID in mock catalog
            "mission": "TESS",
            "period_days": 2.5,
            "epoch_btjd": 1.0,
            "duration_hours": 1.0,
            "depth": 0.01,
            "bls_power": 50.0,
            "snr": 10.0,
            "transit_count": 5
            # Notice we do NOT provide stellar parameters; we expect the pipeline to enrich them!
        }
        
        # We can test the pipeline's /analyze endpoint directly
        lc_payload = {
            "light_curve": {
                "target_id": "99999",
                "mission": "TESS",
                "time": time,
                "flux": flux,
                "flux_error": [0.01] * 100
            },
            "min_period": 1.0,
            "max_period": 5.0
        }
        
        # If we hit /analyze, it does preprocessing, BLS, and enrichment.
        # But BLS on flat noise might not find anything. Let's make a clear transit.
        time_arr = np.array(time)
        flux_arr = np.array(flux)
        # Inject transit
        transit_mask = ((time_arr % 2.5) > 1.0) & ((time_arr % 2.5) < 1.1)
        flux_arr[transit_mask] -= 0.05
        
        lc_payload["light_curve"]["flux"] = flux_arr.tolist()
        
        res = client.post("/pipeline/analyze", json=lc_payload)
        assert res.status_code == 200
        
        candidates = res.json()
        assert len(candidates) > 0
        
        # Verify enrichment happened
        best_cand = candidates[0]
        # The /analyze endpoint returns CandidateResult, which doesn't directly expose stellar radius,
        # but it DOES expose size_class and habitable_zone_proxy which rely on stellar properties!
        # And ops_breakdown contains host_star_suitability.
        
        # Since radius = 1.0, and transit depth = 0.05 (50000 ppm) => Earth size? No, that's huge. 
        # depth 0.05 = (Rp/Rs)^2 = 0.05 => Rp/Rs = 0.22. Rs=1.0 R_sun. Rp = 0.22 R_sun ~ 24 R_earth.
        # This is larger than Jupiter, so size_class should be "Giant".
        assert best_cand["size_class"] != "Unknown"
