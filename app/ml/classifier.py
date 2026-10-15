import os
import joblib
import numpy as np
from pydantic import ValidationError
from app.contracts.models import ClassifiedCandidate, DetectionCandidate, PredictionLabel
from app.features.engineering import build_feature_vector, FEATURE_SCHEMA_VERSION
from app.core.config import settings

class ExoplanetClassifier:
    """Wrapper for the XGBoost classifier."""
    
    def __init__(self, model_path: str | None = None):
        self.model_path = model_path or settings.asteria_model_path
        self.model = None
        self.is_synthetic = False
        
        if self.model_path and os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            self.is_synthetic = bool(getattr(self.model, "is_synthetic", False) or getattr(self.model, "is_demo", False))
        else:
            # Fallback for demonstration / end-to-end pipeline completeness.
            # Strictly marked as synthetic.
            self.is_synthetic = True

    def predict(self, candidate: DetectionCandidate) -> ClassifiedCandidate:
        features = build_feature_vector(candidate)
        
        if self.is_synthetic and self.model is None:
            # Synthetic fallback when no model file is installed: not a real scientific prediction.
            snr_val = features.get("snr")
            prob = 0.8 if (snr_val is not None and not np.isnan(snr_val) and snr_val > 5.0) else 0.2
            model_name = "Synthetic-Mock-Classifier"
            model_version = "0.0.0"
        else:
            import pandas as pd
            df = pd.DataFrame([features])
            
            if hasattr(self.model, "feature_names_in_"):
                model_cols = list(self.model.feature_names_in_)
                for col in model_cols:
                    if col not in df.columns:
                        if col == "secondary_eclipse_power" and "secondary_eclipse_depth" in df.columns:
                            df[col] = df["secondary_eclipse_depth"]
                        elif col == "secondary_eclipse_depth" and "secondary_eclipse_power" in df.columns:
                            df[col] = df["secondary_eclipse_power"]
                        else:
                            df[col] = 0.0
                df = df[model_cols]

                
            df = df.fillna(0)
                
            # Predict probability of class 1 (planet)
            prob = float(self.model.predict_proba(df)[0, 1])
            model_name = getattr(self.model, "model_name", "XGBoost-Exoplanet")
            model_version = getattr(self.model, "version", "1.0")

        label = PredictionLabel.PLANET_CANDIDATE if prob >= 0.5 else PredictionLabel.NON_PLANET
        
        return ClassifiedCandidate(
            candidate=candidate,
            prediction=label,
            planet_probability=prob,
            model_name=model_name,
            model_version=model_version,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            features=features,
            metadata={
                "is_synthetic_prediction": self.is_synthetic,
                "is_scientifically_trained": bool(getattr(self.model, "is_scientifically_trained", False)) if self.model else False,
            }
        )
