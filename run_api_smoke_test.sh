#!/bin/bash
export ASTERIA_TIC_PATH=/Users/deven/Desktop/asteria_data/tic_dec88_00N__90_00N.csv.gz
.venv/bin/uvicorn app.main:app --port 8080 &
SERVER_PID=$!
sleep 3
echo "Server started with PID $SERVER_PID"

curl -v -X POST http://localhost:8080/pipeline/analyze \
  -H 'Content-Type: application/json' \
  -d '{
  "light_curve": {
    "target_id": "TIC 123",
    "mission": "TESS",
    "time": [1.0, 2.0, 3.0, 4.0, 5.0],
    "flux": [1.0, 0.99, 1.0, 0.99, 1.0],
    "flux_error": [0.001, 0.001, 0.001, 0.001, 0.001]
  },
  "min_period": 1.0,
  "max_period": 2.0
}' > response.json 2>&1

cat response.json

kill $SERVER_PID
