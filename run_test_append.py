with open("tests/unit/test_dashboard_api.py", "a") as f:
    f.write("""
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
""")
