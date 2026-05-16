import xgboost as xgb
from sklearn.base import BaseEstimator, ClassifierMixin
import joblib
import os
import pandas as pd
import numpy as np

class XGBoostDetector(BaseEstimator, ClassifierMixin):
    def __init__(self, n_iter=10, random_state=42):
        self.n_iter = n_iter
        self.random_state = random_state
        self.best_estimator_ = None
        self.feature_names_in_ = None
        
    def fit(self, X, y):
        """
        Fit XGBoost directly.
        Optimization disabled due to environment issues with skopt/sklearn.
        Using fixed parameters with scale_pos_weight.
        """
        print("Training XGBoost (Optimization Disabled)...")
        
        # Fixed parameters based on experience/search space
        try:
            self.best_estimator_ = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=10, # Handle imbalance manually
                use_label_encoder=False, 
                eval_metric='logloss', 
                random_state=self.random_state
            )
            self.best_estimator_.fit(X, y)
            print("XGBoost trained successfully.")
        except Exception as e:
            print(f"XGBoost training failed: {e}")
            print("Falling back to RandomForestClassifier...")
            from sklearn.ensemble import RandomForestClassifier
            self.best_estimator_ = RandomForestClassifier(
                n_estimators=200, 
                class_weight='balanced', 
                random_state=self.random_state
            )
            self.best_estimator_.fit(X, y)
        
        if hasattr(X, "columns"):
             self.feature_names_in_ = list(X.columns)
             
        return self

    def predict(self, X):
        return self.best_estimator_.predict(X)
        
    def predict_proba(self, X):
        return self.best_estimator_.predict_proba(X)
        
    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self.best_estimator_, path)
        print(f"Model saved to {path}")
        
    def load(self, path):
        self.best_estimator_ = joblib.load(path)
        print(f"Model loaded from {path}")

if __name__ == "__main__":
    pass
