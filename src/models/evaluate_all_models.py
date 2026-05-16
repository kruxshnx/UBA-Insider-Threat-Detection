"""
Comprehensive Model Evaluation Script
======================================
Evaluates ALL trained models in the UBA Insider Threat Detection system:
  1. Isolation Forest (Baseline)
  2. LSTM Autoencoder
  3. XGBoost (Hybrid)
  4. Bi-LSTM with Attention (Hybrid)

Ground Truth: User U105 after day 25 = malicious insider threat.
"""

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import polars as pl
import joblib
import os
import sys
import json
import logging
from datetime import datetime
from sklearn.metrics import (
    precision_score, recall_score, f1_score, roc_auc_score,
    confusion_matrix, classification_report
)
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from utils.config import config

logger = logging.getLogger("uba.models.evaluate")


def _get_ground_truth_config() -> dict:
    """Read ground truth scenario from config.yaml."""
    data_gen = config.get('data_generation', {})
    scenarios = data_gen.get('scenarios', {})
    return {
        'malicious_user': scenarios.get('malicious_user', 'U105'),
        'malicious_start_day': scenarios.get('malicious_start_day', '2024-01-20'),
    }

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../"))

# Data paths
MASTER_TIMELINE_PATH = os.path.join(PROJECT_ROOT, "data/processed/master_timeline.parquet")
FEATURED_TIMELINE_PATH = os.path.join(PROJECT_ROOT, "data/processed/featured_timeline.csv")

# Model paths
MODEL_DIR_BASELINE = os.path.join(PROJECT_ROOT, "models/baseline")
MODEL_DIR_LSTM = os.path.join(PROJECT_ROOT, "models/lstm")
MODEL_DIR_HYBRID = os.path.join(PROJECT_ROOT, "models/hybrid")

# Output path
RESULTS_FILE = os.path.join(PROJECT_ROOT, "evaluation_results_full.txt")

# Import model classes
from lstm_autoencoder import LSTMAutoencoder
from baseline import BaselineAnomalyDetector
from xgboost_model import XGBoostDetector
from bi_lstm_attention import BiLSTMAttention, InsiderDataset

# LSTM Config (must match training)
SEQ_LEN = 10
HIDDEN_DIM = 32
NUM_LAYERS = 2

# Separator for output formatting
SEP = "=" * 70


def print_header(title):
    """Print a nicely formatted section header."""
    print(f"\n{SEP}")
    print(f"  {title}")
    print(f"{SEP}")


def compute_metrics(y_true, y_pred, y_scores=None, model_name="Model"):
    """Compute and print all metrics for a model. Returns dict of metrics."""
    metrics = {}
    
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    
    metrics['precision'] = prec
    metrics['recall'] = rec
    metrics['f1'] = f1
    metrics['tp'] = int(tp)
    metrics['fp'] = int(fp)
    metrics['tn'] = int(tn)
    metrics['fn'] = int(fn)
    
    print(f"\n  Confusion Matrix:")
    print(f"    TP (True Positives):  {tp:>6}")
    print(f"    FP (False Positives): {fp:>6}")
    print(f"    TN (True Negatives):  {tn:>6}")
    print(f"    FN (False Negatives): {fn:>6}")
    print(f"\n  Metrics:")
    print(f"    Precision: {prec:.4f}")
    print(f"    Recall:    {rec:.4f}")
    print(f"    F1 Score:  {f1:.4f}")
    
    if y_scores is not None:
        try:
            auc = roc_auc_score(y_true, y_scores)
            metrics['roc_auc'] = auc
            print(f"    ROC AUC:   {auc:.4f}")
        except ValueError as e:
            print(f"    ROC AUC:   N/A ({e})")
            metrics['roc_auc'] = None
    else:
        metrics['roc_auc'] = None
    
    print(f"\n  Classification Report:")
    print(classification_report(y_true, y_pred, target_names=["Normal", "Threat"], zero_division=0))
    
    return metrics


# =============================================================================
# 1. ISOLATION FOREST (BASELINE)
# =============================================================================
def evaluate_baseline():
    print_header("1. ISOLATION FOREST (Baseline)")
    
    model_path = os.path.join(MODEL_DIR_BASELINE, "isolation_forest.joblib")
    if not os.path.exists(model_path):
        print("  [SKIP] Model not found.")
        return None
    if not os.path.exists(MASTER_TIMELINE_PATH):
        print("  [SKIP] Data not found.")
        return None
    
    # Load data
    print("  Loading data...")
    df = pl.read_parquet(MASTER_TIMELINE_PATH).to_pandas()
    
    # Load model  
    print("  Loading model...")
    detector = BaselineAnomalyDetector(model_type="isolation_forest")
    detector.load(model_path)
    
    # Preprocess 
    df['hour'] = df['date'].dt.hour
    df['day_of_week'] = df['date'].dt.dayofweek
    features = ['hour', 'day_of_week']
    
    # Load saved scaler if available, otherwise re-fit (legacy fallback)
    baseline_scaler_path = os.path.join(MODEL_DIR_BASELINE, "scaler.joblib")
    if os.path.exists(baseline_scaler_path):
        print("  Loading saved scaler...")
        scaler = joblib.load(baseline_scaler_path)
        X = scaler.transform(df[features])
    else:
        print("  Warning: No saved scaler found, re-fitting (may differ from training)...")
        scaler = StandardScaler()
        X = scaler.fit_transform(df[features])
    
    # Decision scores (lower = more anomalous for IF)
    scores = detector.decision_function(X)
    
    # Threshold
    threshold = scores.mean() - 2 * scores.std()
    print(f"  Score Stats: Mean={scores.mean():.4f}, Std={scores.std():.4f}")
    print(f"  Threshold (Mean - 2*Std): {threshold:.4f}")
    
    y_pred = (scores < threshold).astype(int)
    
    # Ground truth from config
    gt = _get_ground_truth_config()
    start_date = df['date'].min()
    is_threat_time = (df['date'] - start_date).dt.days > 25
    is_target = df['user'] == gt['malicious_user']
    y_true = (is_target & is_threat_time).astype(int)
    
    print(f"  Total samples: {len(y_true)}")
    print(f"  Ground truth anomalies: {y_true.sum()}")
    print(f"  Detected anomalies: {y_pred.sum()}")
    
    # Use negative scores as anomaly scores (higher = more anomalous)
    anomaly_scores = -scores
    
    return compute_metrics(y_true, y_pred, y_scores=anomaly_scores, model_name="Isolation Forest")


# =============================================================================
# 2. LSTM AUTOENCODER
# =============================================================================
def evaluate_lstm_ae():
    print_header("2. LSTM AUTOENCODER")
    
    model_path = os.path.join(MODEL_DIR_LSTM, "lstm_ae.pth")
    scaler_path = os.path.join(MODEL_DIR_LSTM, "scaler.joblib")
    
    if not os.path.exists(model_path):
        print("  [SKIP] Model not found.")
        return None
    if not os.path.exists(scaler_path):
        print("  [SKIP] Scaler not found.")
        return None
    if not os.path.exists(MASTER_TIMELINE_PATH):
        print("  [SKIP] Data not found.")
        return None
    
    # Load data
    print("  Loading data...")
    df = pl.read_parquet(MASTER_TIMELINE_PATH).to_pandas()
    
    # Load scaler
    print("  Loading scaler...")
    scaler = joblib.load(scaler_path)
    
    # Feature engineering (matching training)
    df['hour'] = df['date'].dt.hour
    df['day_of_week'] = df['date'].dt.dayofweek
    source_map = {k: v for v, k in enumerate(df['source'].unique())}
    df['source_idx'] = df['source'].map(source_map)
    feature_cols = ['hour', 'day_of_week', 'source_idx']
    
    # Scale
    df[feature_cols] = scaler.transform(df[feature_cols])
    
    # Ground truth from config
    gt = _get_ground_truth_config()
    start_date = df['date'].min()
    is_threat_time = (df['date'] - start_date).dt.days > 25
    is_target = df['user'] == gt['malicious_user']
    df['is_anomaly'] = (is_target & is_threat_time).astype(int)
    
    # Create sequences
    print("  Creating sequences...")
    sequences = []
    labels = []
    for user, group in df.groupby('user'):
        data = group[feature_cols].values
        lbls = group['is_anomaly'].values
        if len(data) < SEQ_LEN:
            continue
        for i in range(len(data) - SEQ_LEN + 1):
            seq = data[i:i + SEQ_LEN]
            label = 1 if np.any(lbls[i:i + SEQ_LEN]) else 0
            sequences.append(seq)
            labels.append(label)
    
    X_seq = np.array(sequences)
    y_true = np.array(labels)
    
    print(f"  Sequences: {len(X_seq)}")
    if len(X_seq) == 0:
        print("  [SKIP] No sequences created.")
        return None
    
    X_tensor = torch.FloatTensor(X_seq)
    
    # Load model
    print("  Loading model...")
    input_dim = X_seq.shape[2]
    model = LSTMAutoencoder(input_dim=input_dim, hidden_dim=HIDDEN_DIM, num_layers=NUM_LAYERS)
    model.load_state_dict(torch.load(model_path, map_location='cpu', weights_only=True))
    model.eval()
    
    # Predict
    print("  Computing reconstruction errors...")
    with torch.no_grad():
        reconstructed = model(X_tensor)
        diff = (X_tensor - reconstructed) ** 2
        anomaly_scores = diff.mean(dim=(1, 2)).numpy()
    
    # Threshold
    mean_score = np.mean(anomaly_scores)
    std_score = np.std(anomaly_scores)
    threshold = mean_score + 2 * std_score
    
    print(f"  Score Stats: Mean={mean_score:.4f}, Std={std_score:.4f}")
    print(f"  Threshold (Mean + 2*Std): {threshold:.4f}")
    
    y_pred = (anomaly_scores > threshold).astype(int)
    
    print(f"  Total sequences: {len(y_true)}")
    print(f"  Ground truth anomalies: {y_true.sum()}")
    print(f"  Detected anomalies: {y_pred.sum()}")
    
    return compute_metrics(y_true, y_pred, y_scores=anomaly_scores, model_name="LSTM Autoencoder")


# =============================================================================
# 3. XGBOOST (HYBRID)
# =============================================================================
def evaluate_xgboost():
    print_header("3. XGBOOST (Hybrid)")
    
    model_path = os.path.join(MODEL_DIR_HYBRID, "xgboost.joblib")
    scaler_path = os.path.join(MODEL_DIR_HYBRID, "scaler.joblib")
    
    if not os.path.exists(model_path):
        print("  [SKIP] Model not found.")
        return None
    if not os.path.exists(FEATURED_TIMELINE_PATH):
        print("  [SKIP] Data not found.")
        return None
    
    # Load data (matching train_hybrid.py)
    print("  Loading feature data...")
    df_raw = pd.read_csv(FEATURED_TIMELINE_PATH)
    
    users = np.array(df_raw['user'])
    days = np.array(df_raw['day'])
    
    # Create labels from config
    gt = _get_ground_truth_config()
    labels = np.zeros(len(users), dtype=int)
    mask = (users == gt['malicious_user']) & (days > gt['malicious_start_day'])
    labels[mask] = 1
    
    feature_cols = ['far', 'eds', 'iav', 'oaf', 'login_entropy', 'file_count', 'email_count']
    X = np.array([df_raw[col].values for col in feature_cols]).T.astype(float)
    y = labels
    
    # Split (matching training)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    
    # Scale
    print("  Loading scaler...")
    scaler = joblib.load(scaler_path)
    X_test_scaled = scaler.transform(X_test)
    
    # Load model
    print("  Loading model...")
    xgb_model = XGBoostDetector()
    xgb_model.load(model_path)
    
    # Predict
    print("  Predicting...")
    y_pred = xgb_model.predict(X_test)
    
    # Get probabilities for AUC
    y_scores = None
    try:
        y_proba = xgb_model.predict_proba(X_test)
        y_scores = y_proba[:, 1]
    except Exception:
        pass
    
    print(f"  Total test samples: {len(y_test)}")
    print(f"  Ground truth anomalies (test): {y_test.sum()}")
    print(f"  Detected anomalies: {y_pred.sum()}")
    
    return compute_metrics(y_test, y_pred, y_scores=y_scores, model_name="XGBoost")


# =============================================================================
# 4. BI-LSTM WITH ATTENTION (HYBRID)
# =============================================================================
def evaluate_bilstm():
    print_header("4. BI-LSTM WITH ATTENTION (Hybrid)")
    
    model_path = os.path.join(MODEL_DIR_HYBRID, "bilstm.pth")
    scaler_path = os.path.join(MODEL_DIR_HYBRID, "scaler.joblib")
    
    if not os.path.exists(model_path):
        print("  [SKIP] Model not found.")
        return None
    if not os.path.exists(FEATURED_TIMELINE_PATH):
        print("  [SKIP] Data not found.")
        return None
    
    # Load data
    print("  Loading feature data...")
    df_raw = pd.read_csv(FEATURED_TIMELINE_PATH)
    
    users = np.array(df_raw['user'])
    days = np.array(df_raw['day'])
    
    # Create labels from config
    gt = _get_ground_truth_config()
    labels = np.zeros(len(users), dtype=int)
    mask = (users == gt['malicious_user']) & (days > gt['malicious_start_day'])
    labels[mask] = 1
    
    feature_cols = ['far', 'eds', 'iav', 'oaf', 'login_entropy', 'file_count', 'email_count']
    X = np.array([df_raw[col].values for col in feature_cols]).T.astype(float)
    y = labels
    
    # Scale with same scaler as training
    print("  Loading scaler...")
    scaler = joblib.load(scaler_path)
    X_scaled = scaler.transform(X)
    
    # Recreate user split (matching training) but ensure U105 is in test
    unique_users = np.unique(users)
    train_users_list, test_users_list = train_test_split(unique_users, test_size=0.2, random_state=42)
    
    # Ensure malicious user is in test set for meaningful evaluation
    if gt['malicious_user'] not in test_users_list:
        print(f"  Note: {gt['malicious_user']} not in test split, adding for evaluation...")
        test_users_list = np.append(test_users_list, gt['malicious_user'])
        train_users_list = train_users_list[train_users_list != gt['malicious_user']]
    
    # Create sequences (matching training)
    print("  Creating sequences for test users...")
    window_size = 5
    
    seqs = []
    lbls = []
    for u in test_users_list:
        u_indices = np.where(users == u)[0]
        if len(u_indices) == 0:
            continue
        u_days = days[u_indices]
        u_X = X_scaled[u_indices]
        u_y = y[u_indices]
        
        sort_idx = np.argsort(u_days)
        u_X = u_X[sort_idx]
        u_y = u_y[sort_idx]
        
        if len(u_X) < window_size:
            continue
        for i in range(len(u_X) - window_size + 1):
            window = u_X[i:i + window_size]
            window_lbl = u_y[i + window_size - 1]
            seqs.append(window)
            lbls.append(window_lbl)
    
    X_seq_test = np.array(seqs)
    y_test = np.array(lbls)
    
    if len(X_seq_test) == 0:
        print("  [SKIP] No test sequences.")
        return None
    
    print(f"  Test sequences: {len(X_seq_test)}")
    
    # Load model
    print("  Loading model...")
    input_dim = X.shape[1]
    model = BiLSTMAttention(input_dim=input_dim, hidden_dim=16)
    model.load_state_dict(torch.load(model_path, map_location='cpu', weights_only=True))
    model.eval()
    
    # Predict
    print("  Predicting...")
    X_tensor = torch.FloatTensor(X_seq_test)
    with torch.no_grad():
        outputs, attn_weights = model(X_tensor)
        probabilities = torch.softmax(outputs, dim=1).numpy()
        y_pred = np.argmax(probabilities, axis=1)
        y_scores = probabilities[:, 1]  # threat probability
    
    print(f"  Total test sequences: {len(y_test)}")
    print(f"  Ground truth anomalies (test): {y_test.sum()}")
    print(f"  Detected anomalies: {y_pred.sum()}")
    
    return compute_metrics(y_test, y_pred, y_scores=y_scores, model_name="Bi-LSTM Attention")


# =============================================================================
# MAIN
# =============================================================================
def main():
    print(f"\n{'#' * 70}")
    print(f"  UBA INSIDER THREAT DETECTION - COMPREHENSIVE MODEL EVALUATION")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#' * 70}")
    
    all_results = {}
    
    # Run each evaluation
    result = evaluate_baseline()
    if result:
        all_results['Isolation Forest'] = result
    
    result = evaluate_lstm_ae()
    if result:
        all_results['LSTM Autoencoder'] = result
    
    result = evaluate_xgboost()
    if result:
        all_results['XGBoost'] = result
    
    result = evaluate_bilstm()
    if result:
        all_results['Bi-LSTM Attention'] = result
    
    # Comparison Summary
    print_header("COMPARATIVE SUMMARY")
    
    if all_results:
        # Build comparison table
        header = f"{'Model':<25} | {'Precision':>10} | {'Recall':>10} | {'F1':>10} | {'ROC AUC':>10} | {'TP':>5} | {'FP':>5} | {'FN':>5}"
        print(f"\n  {header}")
        print(f"  {'-' * len(header)}")
        
        for name, m in all_results.items():
            auc_str = f"{m['roc_auc']:.4f}" if m.get('roc_auc') is not None else "  N/A"
            row = f"{name:<25} | {m['precision']:>10.4f} | {m['recall']:>10.4f} | {m['f1']:>10.4f} | {auc_str:>10} | {m['tp']:>5} | {m['fp']:>5} | {m['fn']:>5}"
            print(f"  {row}")
        
        # Best model
        best_f1_model = max(all_results.items(), key=lambda x: x[1]['f1'])
        best_auc_models = {k: v for k, v in all_results.items() if v.get('roc_auc') is not None}
        
        print(f"\n  Best Model by F1 Score: {best_f1_model[0]} (F1={best_f1_model[1]['f1']:.4f})")
        
        if best_auc_models:
            best_auc = max(best_auc_models.items(), key=lambda x: x[1]['roc_auc'])
            print(f"  Best Model by ROC AUC:  {best_auc[0]} (AUC={best_auc[1]['roc_auc']:.4f})")
    else:
        print("  No models were successfully evaluated.")
    
    # Save to file
    print(f"\n  Saving results to {RESULTS_FILE}...")
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        f.write("UBA INSIDER THREAT DETECTION - MODEL EVALUATION RESULTS\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")
        
        for name, m in all_results.items():
            f.write(f"MODEL: {name}\n")
            f.write(f"  Precision: {m['precision']:.4f}\n")
            f.write(f"  Recall:    {m['recall']:.4f}\n")
            f.write(f"  F1 Score:  {m['f1']:.4f}\n")
            auc_val = f"{m['roc_auc']:.4f}" if m.get('roc_auc') is not None else "N/A"
            f.write(f"  ROC AUC:   {auc_val}\n")
            f.write(f"  TP={m['tp']}, FP={m['fp']}, TN={m['tn']}, FN={m['fn']}\n\n")
        
        if all_results:
            best = max(all_results.items(), key=lambda x: x[1]['f1'])
            f.write(f"\nBEST MODEL (by F1): {best[0]} with F1={best[1]['f1']:.4f}\n")
    
    print("  Done!")


if __name__ == "__main__":
    main()
