"""
Analysis router — per-user risk history, SHAP explanations, and analyst feedback.
Uses centralised settings instead of hardcoded paths.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pandas as pd
import numpy as np
import os
import joblib
import hashlib
import logging
from datetime import datetime

from src.api.config import settings
from src.risk_engine.bayesian_network import bayesian_network, nonlinear_aggregator
from src.models.thresholding import adaptive_threshold, drift_detector
from src.security.privacy import pseudonymization, access_control, cryptographic_erasure
from src.deployment.operations import shadow_deployment, synthetic_generator

# SHAP explainer (best-effort import)
try:
    from src.models.explainability import SHAPExplainer
except ImportError:
    SHAPExplainer = None

logger = logging.getLogger("uba.analysis")

router = APIRouter()

# ── Paths (from unified settings) ───────────────────────────────────────────
DATA_PATH = os.path.join(settings.PROCESSED_DATA_DIR, "featured_timeline.csv")
MODEL_DIR = os.path.join(settings.MODELS_DIR, "hybrid")

# ── Lazy-loaded resources ───────────────────────────────────────────────────
_xgboost_model = None
_explainer = None


def _load_resources():
    """Load XGBoost model and SHAP explainer once on first call."""
    global _xgboost_model, _explainer
    if _xgboost_model is not None:
        return

    model_path = os.path.join(MODEL_DIR, "xgboost.joblib")
    if not os.path.exists(model_path):
        logger.warning("XGBoost model not found at %s", model_path)
        return

    try:
        _xgboost_model = joblib.load(model_path)
        logger.info("Loaded XGBoost model from %s", model_path)
        if SHAPExplainer is not None:
            _explainer = SHAPExplainer(model_path=model_path)
            logger.info("SHAP explainer initialised.")
        else:
            logger.warning("SHAP not available — explainability endpoint disabled.")
    except Exception as e:
        logger.error("Failed to load models: %s", e)


# ── Feature columns ────────────────────────────────────────────────────────
FEATURE_COLS = [
    "far", "eds", "iav", "oaf",
    "login_entropy", "file_count", "email_count",
]


# ── Schemas ──────────────────────────────────────────────────────────────────
class FeedbackRequest(BaseModel):
    user_id: str
    day: str
    is_false_positive: bool


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.get("/analysis/user/{user_id}")
async def get_user_risk(user_id: str):
    """
    Return the daily risk history for a specific user.

    Loads the featured timeline, applies the XGBoost model to compute
    risk scores per day, and returns the full history sorted by date.
    """
    _load_resources()

    if not os.path.exists(DATA_PATH):
        raise HTTPException(status_code=404, detail="Feature data source not found.")

    try:
        df = pd.read_csv(DATA_PATH)
        user_df = df[df["user"] == user_id].copy()

        if user_df.empty:
            return {"user_id": user_id, "history": []}

        # Predict risk scores
        if _xgboost_model is not None:
            valid_cols = [c for c in FEATURE_COLS if c in user_df.columns]
            if not valid_cols:
                return {"user_id": user_id, "history": [], "error": "Missing feature columns."}

            X = user_df[valid_cols].fillna(0)
            probs = _xgboost_model.predict_proba(X)[:, 1]
            user_df["risk_score"] = (probs * 100).astype(int)
        else:
            user_df["risk_score"] = 0

        # Build response
        history = []
        for _, row in user_df.iterrows():
            # Deterministic pseudo-IP per user+date (for display only)
            seed = f"{row['user']}_{row['day']}"
            h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
            ip = f"{10 + (h % 180)}.{(h >> 8) % 256}.{(h >> 16) % 256}.{(h >> 24) % 254 + 1}"

            history.append({
                "date": str(row["day"]),
                "risk_score": int(row["risk_score"]),
                "ip": ip,
                "far": round(float(row.get("far", 0)), 3),
                "eds": round(float(row.get("eds", 0)), 3),
                "iav": round(float(row.get("iav", 0)), 3),
                "oaf": round(float(row.get("oaf", 0)), 3),
                "login_entropy": round(float(row.get("login_entropy", 0)), 3),
                "file_count": int(row.get("file_count", 0)),
                "email_count": int(row.get("email_count", 0)),
            })

        history.sort(key=lambda x: x["date"], reverse=True)
        return {"user_id": user_id, "history": history}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error computing risk for user %s", user_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/explain/{user_id}/{date}")
async def explain_risk(user_id: str, date: str):
    """
    Return SHAP-based feature-importance explanation for a user on a given date.

    Requires the XGBoost model and SHAP library to be available.
    """
    _load_resources()

    if _explainer is None:
        raise HTTPException(
            status_code=503,
            detail="SHAP explainer is not initialised. Ensure the model and SHAP are available.",
        )

    try:
        df = pd.read_csv(DATA_PATH)
        df["day_str"] = df["day"].astype(str)

        row = df[(df["user"] == user_id) & (df["day_str"] == date)]
        if row.empty:
            raise HTTPException(status_code=404, detail="No data for this user/date combination.")

        valid_cols = [c for c in FEATURE_COLS if c in row.columns]
        X_instance = row[valid_cols].iloc[0]

        explanation = _explainer.explain_local(X_instance)
        return {"explanation": explanation}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error generating explanation for %s on %s", user_id, date)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    """
    Submit analyst feedback (e.g. mark a detection as false positive).

    Feedback is saved to a CSV file for future model retraining.
    """
    feedback_path = os.path.join(settings.FEEDBACK_DIR, "feedback.csv")
    try:
        new_row = pd.DataFrame([feedback.model_dump()])
        header = not os.path.exists(feedback_path)
        new_row.to_csv(feedback_path, mode="a", header=header, index=False)
        logger.info("Feedback received: user=%s day=%s fp=%s", feedback.user_id, feedback.day, feedback.is_false_positive)
        return {"status": "success", "message": "Feedback recorded."}
    except Exception as e:
        logger.error("Failed to save feedback: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ENHANCED ANALYSIS ENDPOINTS (Bayesian, Drift Detection, Privacy)
# =============================================================================

class RiskDistributionRequest(BaseModel):
    """Request for Bayesian risk distribution."""
    user_id: str
    activity: str
    hour: int
    role: str = "Employee"
    anomaly_score: float
    model_type: str = "lstm"


@router.post("/analysis/risk-distribution")
async def calculate_risk_distribution(request: RiskDistributionRequest):
    """
    Calculate Bayesian risk distribution for an event.
    
    Returns probability distribution instead of point estimate,
    providing uncertainty quantification.
    """
    try:
        row = pd.Series({
            'user': request.user_id,
            'activity': request.activity,
            'hour': request.hour,
            'role': request.role
        })
        
        risk_dist = bayesian_network.calculate_risk_distribution(
            row, 
            request.anomaly_score,
            request.model_type
        )
        
        return {
            "status": "success",
            "risk_distribution": risk_dist.to_dict(),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.exception("Risk distribution calculation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/drift-status")
async def check_concept_drift():
    """
    Check if current data shows concept drift from training distribution.
    """
    try:
        # Load recent anomaly scores (simulated for now)
        recent_scores = np.random.normal(0.2, 0.1, 500)
        
        result = drift_detector.detect_drift(recent_scores)
        
        return {
            "status": "success",
            "drift_detected": result['drift_detected'],
            "confidence": result['confidence'],
            "metrics": result['metrics'],
            "recommendation": result['recommendation']
        }
    
    except Exception as e:
        logger.exception("Drift detection failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/update-threshold")
async def update_threshold(method: str = "percentile"):
    """
    Update anomaly detection threshold using adaptive method.
    
    Methods: percentile, evt, cost, iqr, std
    """
    try:
        scores = np.random.normal(0.2, 0.1, 1000)  # Simulated
        result = adaptive_threshold.calculate_threshold(scores, method=method)
        
        return {
            "status": "success",
            "threshold": result.threshold,
            "method": result.method,
            "confidence": result.confidence,
            "metadata": result.metadata
        }
    
    except Exception as e:
        logger.exception("Threshold update failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthetic/generate")
async def generate_synthetic_data(
    scenario: str = "data_exfiltration",
    intensity: float = 1.0,
    n_samples: int = 100
):
    """
    Generate synthetic threat scenario data.
    """
    try:
        synthetic = synthetic_generator._create_synthetic_events(
            scenario=scenario,
            user_id="synthetic_user",
            intensity=intensity
        )
        
        return {
            "status": "success",
            "scenario": scenario,
            "event_count": len(synthetic),
            "events": synthetic.to_dict(orient='records') if len(synthetic) > 0 else []
        }
    
    except Exception as e:
        logger.exception("Synthetic data generation failed")
        raise HTTPException(status_code=500, detail=str(e))
