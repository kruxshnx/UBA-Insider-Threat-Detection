import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.base import BaseEstimator, OutlierMixin
from typing import Literal
import joblib
import os

class BaselineAnomalyDetector:
    """
    Wrapper for Baseline Anomaly Detection Models (Isolation Forest, OCSVM).
    """

    def __init__(self, model_type: Literal["isolation_forest", "ocsvm"] = "isolation_forest", **kwargs):
        self.model_type = model_type
        self.model = None
        self.kwargs = kwargs

        if self.model_type == "isolation_forest":
            self.model = IsolationForest(**self.kwargs)
        elif self.model_type == "ocsvm":
            self.model = OneClassSVM(**self.kwargs)
        else:
            raise ValueError(f"Unknown model type: {model_type}")

    def fit(self, X: pd.DataFrame):
        """
        Fit the model to the data. 
        Note: For OCSVM and IF, we usually fit on 'normal' data or the whole dataset 
        assuming anomalies are rare.
        """
        print(f"Training {self.model_type}...")
        self.model.fit(X)
        print("Training complete.")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict anomalies.
        Returns: 
            -1 for outliers (anomalies)
             1 for inliers (normal)
        """
        return self.model.predict(X)

    def decision_function(self, X: pd.DataFrame) -> np.ndarray:
        """
        Average anomaly score of X of the base classifiers.
        The anomaly score of an input sample is computed as
        the mean anomaly score of the trees in the forest.
        
        For IsolationForest:
        The measure of normality of an observation described by the
        path length of the case.
        
        Lower scores = More Anomalous (usually). 
        sklearn returns negative scores for outliers in decision_function usually.
        """
        return self.model.decision_function(X)

    def save(self, path: str):
        """Save model to disk."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self.model, path)
        print(f"Model saved to {path}")

    def load(self, path: str):
        """Load model from disk."""
        self.model = joblib.load(path)
        print(f"Model loaded from {path}")
