import re

with open("app/ml/classifier.py", "r") as f:
    code = f.read()

# Add config import and use it
if "from app.core.config import settings" not in code:
    code = code.replace(
        'from app.features.engineering import build_feature_vector, FEATURE_SCHEMA_VERSION',
        'from app.features.engineering import build_feature_vector, FEATURE_SCHEMA_VERSION\nfrom app.core.config import settings'
    )

code = code.replace(
    'self.model_path = model_path or os.environ.get("ASTERIA_MODEL_PATH")',
    'self.model_path = model_path or settings.asteria_model_path'
)

with open("app/ml/classifier.py", "w") as f:
    f.write(code)

