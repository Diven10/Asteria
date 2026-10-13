import requests
import time
import subprocess
import os
import signal

os.environ["ASTERIA_TIC_PATH"] = "/Users/deven/Desktop/asteria_data/tic_dec88_00N__90_00N.csv.gz"

proc = subprocess.Popen([".venv/bin/uvicorn", "app.main:app", "--port", "8080"])
time.sleep(3) # Wait for startup

try:
    res = requests.post(
        "http://localhost:8080/pipeline/analyze",
        json={
            "light_curve": {
                "target_id": "TIC 123",
                "mission": "TESS",
                "time": [1.0, 2.0, 3.0, 4.0, 5.0],
                "flux": [1.0, 0.99, 1.0, 0.99, 1.0],
                "flux_error": [0.001, 0.001, 0.001, 0.001, 0.001]
            },
            "min_period": 1.0,
            "max_period": 2.0
        }
    )
    print("STATUS CODE:", res.status_code)
    print("RESPONSE:", res.json())
finally:
    proc.send_signal(signal.SIGINT)
    proc.wait()
