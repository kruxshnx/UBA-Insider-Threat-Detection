import shap
import joblib
import pandas as pd
import numpy as np
import os
import sys

# Add parent to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from data_pipeline.preprocessing import PROJECT_ROOT

class SHAPExplainer:
    def __init__(self, model_path=None, data_path=None):
        if model_path is None:
            model_path = os.path.join(PROJECT_ROOT, "models/hybrid/xgboost.joblib")
        
        print(f"Loading model from {model_path}")
        self.model = joblib.load(model_path)
        
        # Initialize explainer
        # TreeExplainer is best for XGBoost
        self.explainer = shap.TreeExplainer(self.model)
        
    def explain_local(self, X_instance):
        """
        Explain a single prediction.
        Args:
            X_instance: DataFrame or Series (single row)
        Returns:
            dict: {feature: shap_value} sorted by importance
        """
        shap_values = self.explainer.shap_values(X_instance)
        
        # If binary classification, shap_values might be a list or array
        if isinstance(shap_values, list):
            shap_values = shap_values[1] # Positive class
            
        # Create dict
        if isinstance(X_instance, pd.Series):
            features = X_instance.index
            values = shap_values
        else:
            features = X_instance.columns
            values = shap_values[0] # Assume single row input
            
        explanation = dict(zip(features, values))
        
        # Sort by absolute value
        sorted_explanation = dict(sorted(explanation.items(), key=lambda item: abs(item[1]), reverse=True))
        
        return sorted_explanation

    def explain_global(self, X_background):
        """
        Global feature importance.
        """
        shap_values = self.explainer.shap_values(X_background)
        return np.abs(shap_values).mean(0)

if __name__ == "__main__":
    # Test
    pass
