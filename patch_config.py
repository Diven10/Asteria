import re

with open("app/core/config.py", "r") as f:
    code = f.read()

# Add asteria_model_path to Settings
code = code.replace(
    'environment: str = "development"',
    'environment: str = "development"\n    asteria_model_path: str = "app/ml/models/baseline.joblib"'
)

with open("app/core/config.py", "w") as f:
    f.write(code)

