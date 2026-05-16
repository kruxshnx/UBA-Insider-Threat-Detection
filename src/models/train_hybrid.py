"""
Hybrid Model Training Pipeline.

Trains three ML models for insider threat detection:
  1. Isolation Forest (unsupervised baseline)
  2. XGBoost (supervised classifier)
  3. Bi-LSTM with Attention (sequential classifier)

Ground truth labels and feature columns are driven by config.yaml.
Errors terminate the pipeline instead of writing corrupt model files.
"""

import pandas as pd
import numpy as np
import os
import sys
import logging
import joblib
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report

# Add parent to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models.baseline import BaselineAnomalyDetector
from models.xgboost_model import XGBoostDetector
from models.bi_lstm_attention import BiLSTMAttention, InsiderDataset
from utils.config import config

logger = logging.getLogger("uba.models.train_hybrid")

# ── Paths (from config-aware project root) ───────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../"))
PROCESSED_DATA_PATH = os.path.join(PROJECT_ROOT, "data/processed/featured_timeline.csv")
MODEL_SAVE_DIR = os.path.join(PROJECT_ROOT, "models/hybrid")
os.makedirs(MODEL_SAVE_DIR, exist_ok=True)

# ── Config-driven constants ──────────────────────────────────────────────────
FEATURE_COLS = ['far', 'eds', 'iav', 'oaf', 'login_entropy', 'file_count', 'email_count']


def _get_ground_truth_config() -> dict:
    """
    Read ground truth scenario config from config.yaml → data_generation → scenarios.

    Falls back to legacy defaults if the section doesn't exist yet.
    """
    data_gen = config.get('data_generation', {})
    scenarios = data_gen.get('scenarios', {})

    malicious_user = scenarios.get('malicious_user', 'U105')
    malicious_start_day = scenarios.get('malicious_start_day', '2024-01-20')

    return {
        'malicious_user': malicious_user,
        'malicious_start_day': malicious_start_day,
    }


def load_data():
    """Load feature data and create ground-truth labels from config."""
    logger.info("Loading feature data from %s", PROCESSED_DATA_PATH)

    if not os.path.exists(PROCESSED_DATA_PATH):
        raise FileNotFoundError(f"Feature data not found: {PROCESSED_DATA_PATH}")

    df_raw = pd.read_csv(PROCESSED_DATA_PATH)
    logger.info("CSV loaded: %d rows, %d columns", len(df_raw), len(df_raw.columns))

    users = np.array(df_raw['user'])
    days = np.array(df_raw['day'])

    # ── Ground truth from config ──────────────────────────────────────────
    gt = _get_ground_truth_config()
    labels = np.zeros(len(users), dtype=int)
    mask = (users == gt['malicious_user']) & (days > gt['malicious_start_day'])
    labels[mask] = 1

    logger.info(
        "Ground truth: user=%s after %s → %d malicious instances out of %d total",
        gt['malicious_user'], gt['malicious_start_day'], np.sum(labels), len(labels),
    )

    # ── Feature matrix ────────────────────────────────────────────────────
    available_cols = [c for c in FEATURE_COLS if c in df_raw.columns]
    if not available_cols:
        raise ValueError(f"No feature columns found. Expected: {FEATURE_COLS}")

    X = df_raw[available_cols].values.astype(float)
    y = labels

    logger.info("X shape: %s, y shape: %s", X.shape, y.shape)
    return X, y, users, days


def create_sequences(users, days, X_scaled, y, target_users, window_size=5):
    """Create sliding-window sequences for sequential models."""
    seqs = []
    lbls = []

    for u in target_users:
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
            seqs.append(u_X[i:i + window_size])
            lbls.append(u_y[i + window_size - 1])

    return np.array(seqs), np.array(lbls)


def train_pipeline():
    """Run the full training pipeline for all three model types."""
    logger.info("=" * 60)
    logger.info("Starting Hybrid Training Pipeline")
    logger.info("=" * 60)

    X, y, users, days = load_data()

    # ── Train/Test Split ──────────────────────────────────────────────────
    logger.info("Splitting data (80/20, stratified)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    # ── Scaling ───────────────────────────────────────────────────────────
    logger.info("Fitting scaler...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    joblib.dump(scaler, os.path.join(MODEL_SAVE_DIR, "scaler.joblib"))

    # ── 1. Isolation Forest (Unsupervised) ────────────────────────────────
    logger.info("")
    logger.info("--- Training Isolation Forest ---")
    try:
        iforest = BaselineAnomalyDetector(
            model_type="isolation_forest", contamination=0.04, random_state=42
        )
        iforest.fit(X_train_scaled)
        iforest.save(os.path.join(MODEL_SAVE_DIR, "iforest.joblib"))

        if_preds = iforest.predict(X_test_scaled)
        if_preds_binary = np.where(if_preds == -1, 1, 0)
        logger.info("Isolation Forest Report:\n%s",
                     classification_report(y_test, if_preds_binary, zero_division=0))
    except Exception as e:
        logger.error("Isolation Forest training FAILED: %s", e, exc_info=True)
        raise  # FAIL FAST — do not write dummy files

    # ── 2. XGBoost (Supervised) ───────────────────────────────────────────
    logger.info("")
    logger.info("--- Training XGBoost ---")
    try:
        xgb_model = XGBoostDetector(n_iter=5)
        xgb_model.fit(X_train, y_train)
        xgb_model.save(os.path.join(MODEL_SAVE_DIR, "xgboost.joblib"))

        xgb_preds = xgb_model.predict(X_test)
        logger.info("XGBoost Report:\n%s",
                     classification_report(y_test, xgb_preds, zero_division=0))
    except Exception as e:
        logger.error("XGBoost training FAILED: %s", e, exc_info=True)
        raise  # FAIL FAST

    # ── 3. Bi-LSTM with Attention (Sequential) ───────────────────────────
    logger.info("")
    logger.info("--- Training Bi-LSTM ---")
    try:
        X_scaled = scaler.transform(X)

        unique_users = np.unique(users)
        train_users_list, test_users_list = train_test_split(
            unique_users, test_size=0.2, random_state=42
        )

        logger.info("Creating sequences...")
        X_seq_train, y_seq_train = create_sequences(
            users, days, X_scaled, y, train_users_list
        )
        X_seq_test, y_seq_test = create_sequences(
            users, days, X_scaled, y, test_users_list
        )
        logger.info("Sequences: Train %d, Test %d", len(X_seq_train), len(X_seq_test))

        if len(X_seq_train) == 0:
            logger.warning("No training sequences created — skipping Bi-LSTM.")
        else:
            train_ds = InsiderDataset(X_seq_train, y_seq_train)
            test_ds = InsiderDataset(X_seq_test, y_seq_test)

            train_loader = DataLoader(train_ds, batch_size=32, shuffle=True)
            test_loader = DataLoader(test_ds, batch_size=32)

            model = BiLSTMAttention(input_dim=X.shape[1], hidden_dim=16)
            criterion = nn.CrossEntropyLoss(weight=torch.tensor([1.0, 10.0]))
            optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

            logger.info("Starting Bi-LSTM Training Loop (10 epochs)...")
            for epoch in range(10):
                model.train()
                total_loss = 0
                for X_batch, y_batch in train_loader:
                    optimizer.zero_grad()
                    outputs, attn = model(X_batch)
                    loss = criterion(outputs, y_batch.squeeze())
                    loss.backward()
                    optimizer.step()
                    total_loss += loss.item()
                if epoch % 2 == 0:
                    logger.info("Epoch %d: Loss %.4f", epoch, total_loss / len(train_loader))

            torch.save(model.state_dict(), os.path.join(MODEL_SAVE_DIR, "bilstm.pth"))
            logger.info("Bi-LSTM model saved.")

            # Evaluate
            model.eval()
            all_preds = []
            all_labels = []
            with torch.no_grad():
                for X_batch, y_batch in test_loader:
                    outputs, attn = model(X_batch)
                    preds = outputs.argmax(dim=1)
                    all_preds.extend(preds.numpy())
                    all_labels.extend(y_batch.squeeze().numpy())

            logger.info("Bi-LSTM Test Report:\n%s",
                         classification_report(all_labels, all_preds,
                                               target_names=["Normal", "Threat"],
                                               zero_division=0))

    except Exception as e:
        logger.error("Bi-LSTM training FAILED: %s", e, exc_info=True)
        raise  # FAIL FAST

    logger.info("=" * 60)
    logger.info("Training pipeline completed successfully.")
    logger.info("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    train_pipeline()
