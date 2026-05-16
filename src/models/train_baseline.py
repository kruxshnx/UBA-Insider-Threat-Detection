import pandas as pd
import polars as pl
import argparse
import os
import sys
import joblib
from .baseline import BaselineAnomalyDetector
from sklearn.preprocessing import StandardScaler

# Add parent directory to path to allow importing from data_pipeline if needed
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../"))
PROCESSED_DATA_PATH = os.path.join(PROJECT_ROOT, "data/processed/master_timeline.parquet")
MODEL_SAVE_DIR = os.path.join(PROJECT_ROOT, "models/baseline")

def load_data():
    """Load and preprocess data for training."""
    if not os.path.exists(PROCESSED_DATA_PATH):
        print(f"Error: Data file not found at {PROCESSED_DATA_PATH}")
        print("Please run data_pipeline/generator.py and normalization.py first.")
        sys.exit(1)

    print("Loading data...")
    df = pl.read_parquet(PROCESSED_DATA_PATH)
    
    # Feature Engineering for Baseline (Simple count-based features)
    # We aggregate by User and Day to create a feature vector per user-day
    # (Or window based). For baseline, let's just do simple categorical encoding of activity
    # on a per-event basis is hard for IsolationForest to capture sequence.
    # LET'S AGGREGATE: Count events per user per hour.
    
    # Cast to pandas for easy sklearn usage for now
    pdf = df.to_pandas()
    pdf['hour'] = pdf['date'].dt.hour
    
    # pivot/groupby to get features?
    # For simplicity of this baseline demo:
    # We will just extract numerical features: [hour, day_of_week] 
    # and maybe OneHotEncode 'source'
    
    pdf['day_of_week'] = pdf['date'].dt.dayofweek
    
    # One-Hot Encoding 'source' and 'activity' usually creates too many dims if high cardinality.
    # keeping it simple: hour, day_of_week.
    # In a real scenario, we'd have count of file ops, count of logons, etc.
    
    features = ['hour', 'day_of_week']
    X = pdf[features].copy()
    
    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    return X_scaled, scaler

def train(model_name="isolation_forest"):
    X, scaler = load_data()
    
    detector = BaselineAnomalyDetector(model_type=model_name, n_estimators=100, contamination=0.05, random_state=42)
    detector.fit(X)
    
    # Save model and scaler
    os.makedirs(MODEL_SAVE_DIR, exist_ok=True)
    detector.save(f"{MODEL_SAVE_DIR}/{model_name}.joblib")
    joblib.dump(scaler, os.path.join(MODEL_SAVE_DIR, "scaler.joblib"))
    print(f"Scaler saved to {MODEL_SAVE_DIR}/scaler.joblib")
    
    # Evaluated on training set (just for demo)
    # scores = detector.decision_function(X)
    # print(f"Mean Anomaly Score: {scores.mean()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["isolation_forest", "ocsvm"], default="isolation_forest")
    args = parser.parse_args()
    
    train(args.model)
