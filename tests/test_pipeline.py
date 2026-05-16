import pytest
import os
import pandas as pd

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../"))
DATA_DIR = os.path.join(PROJECT_ROOT, "data/raw")
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data/processed")
MODEL_DIR = os.path.join(PROJECT_ROOT, "models")
RISK_DIR = os.path.join(PROJECT_ROOT, "data/risk_output")

class TestPipelineIntegration:
    def test_data_generation_artifacts(self):
        """Check if raw data CSVs exist."""
        assert os.path.exists(os.path.join(DATA_DIR, "logon.csv"))
        assert os.path.exists(os.path.join(DATA_DIR, "file.csv"))
        assert os.path.exists(os.path.join(DATA_DIR, "users.csv"))

    def test_normalization_artifacts(self):
        """Check if master timeline parquet exists."""
        master_path = os.path.join(PROCESSED_DIR, "master_timeline.parquet")
        assert os.path.exists(master_path)
        # Check explicit columns
        df = pd.read_parquet(master_path)
        assert "activity" in df.columns
        assert "user" in df.columns

    def test_model_artifacts_baseline(self):
        """Check Baseline model exists."""
        assert os.path.exists(os.path.join(MODEL_DIR, "baseline/isolation_forest.joblib"))

    def test_model_artifacts_lstm(self):
        """Check at least one LSTM model exists (global or role-specific)."""
        lstm_dir = os.path.join(MODEL_DIR, "lstm")
        # The pipeline may produce lstm_ae.pth (v1) or lstm_global.pth (v2)
        has_lstm = (
            os.path.exists(os.path.join(lstm_dir, "lstm_ae.pth")) or
            os.path.exists(os.path.join(lstm_dir, "lstm_global.pth")) or
            os.path.exists(os.path.join(lstm_dir, "lstm_employee.pth"))
        )
        assert has_lstm, f"No LSTM model found in {lstm_dir}"

    def test_risk_report_artifact(self):
        """Check Risk Report was generated and has content."""
        # Pipeline v2 writes risk_report_events.csv; v1 wrote risk_report.csv
        report_path = os.path.join(RISK_DIR, "risk_report_events.csv")
        if not os.path.exists(report_path):
            report_path = os.path.join(RISK_DIR, "risk_report.csv")
        assert os.path.exists(report_path), "No risk report CSV found"
        
        df = pd.read_csv(report_path)
        assert not df.empty
        assert "risk_score" in df.columns
        
        # Verify we caught some high risk events
        high_risk = df[df['risk_score'] > 50]
        assert len(high_risk) > 0, "No high risk events found in report!"
