import pandas as pd
import numpy as np
from typing import Any, Dict
from pydantic import BaseModel

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

from app.contracts.models import ClassifiedCandidate

class ShapExplanation(BaseModel):
    """Clean serializable schema for per-candidate SHAP explanations."""
    is_valid: bool = True
    error_message: str | None = None
    feature_contributions: Dict[str, float] = {}
    base_value: float | None = None
    predicted_value: float | None = None
    feature_schema_version: str = ""
    model_name: str = ""
    model_version: str = ""

class GlobalImportance(BaseModel):
    """Clean serializable schema for global feature importance."""
    is_valid: bool = True
    error_message: str | None = None
    importance: Dict[str, float] = {}

class ShapExplainer:
    def __init__(self, model: Any = None):
        self.model = model
        self.explainer = None
        self.init_error = None
        
        if not SHAP_AVAILABLE:
            self.init_error = "SHAP library is not installed or available."
            return
            
        if self.model is None:
            self.init_error = "A trained model must be provided to ShapExplainer."
            return
            
        try:
            self.explainer = shap.TreeExplainer(self.model)
        except Exception as e:
            self.init_error = f"Failed to initialize TreeExplainer: {e}"

    def explain(self, classified: ClassifiedCandidate) -> ShapExplanation:
        """Generates SHAP explanations for a single classified candidate."""
        if self.init_error is not None:
            return ShapExplanation(
                is_valid=False,
                error_message=self.init_error
            )
            
        features = classified.features
        
        if not features:
            return ShapExplanation(
                is_valid=False,
                error_message="Candidate has no features to explain."
            )
            
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

        
        try:
            shap_values = self.explainer.shap_values(df)
            
            # Handle different SHAP output shapes based on the model (e.g. XGBoost vs RandomForest)
            if isinstance(shap_values, list):
                vals = shap_values[1][0]  # Take class 1 (planet)
                expected_val = self.explainer.expected_value[1]
            elif len(shap_values.shape) == 3:
                # shap >= 0.39 for RandomForest might return (1, n_features, n_classes)
                vals = shap_values[0, :, 1]
                expected_val = self.explainer.expected_value[1]
            else:
                # XGBoost binary classification returns (1, n_features)
                vals = shap_values[0]
                expected_val = self.explainer.expected_value
                if isinstance(expected_val, (list, tuple, np.ndarray)):
                    expected_val = expected_val[0]
                    
            # Compute predicted log-odds (base + sum of SHAP values)
            pred_value = float(expected_val) + sum(float(v) for v in vals)
            
            importance = {str(k): float(v) for k, v in zip(features.keys(), vals)}
            
            return ShapExplanation(
                is_valid=True,
                feature_contributions=importance,
                base_value=float(expected_val),
                predicted_value=float(pred_value),
                feature_schema_version=classified.feature_schema_version,
                model_name=classified.model_name,
                model_version=classified.model_version
            )
            
        except Exception as e:
            return ShapExplanation(
                is_valid=False,
                error_message=f"SHAP explanation failed: {e}"
            )

    def get_global_importance(self, feature_names: list[str]) -> GlobalImportance:
        """
        Retrieves global feature importance from the tree model.
        Instead of running SHAP over a large dataset, we can extract the native 
        feature importances from the tree model (which XGBoost/RF compute).
        """
        try:
            if hasattr(self.model, "feature_importances_"):
                importances = self.model.feature_importances_
                imp_dict = {str(name): float(imp) for name, imp in zip(feature_names, importances)}
                return GlobalImportance(is_valid=True, importance=imp_dict)
            else:
                return GlobalImportance(
                    is_valid=False,
                    error_message="Model does not expose feature_importances_."
                )
        except Exception as e:
            return GlobalImportance(
                is_valid=False,
                error_message=f"Failed to extract global importance: {e}"
            )
