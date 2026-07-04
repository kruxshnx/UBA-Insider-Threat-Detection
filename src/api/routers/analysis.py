"""
Analysis router — per-user risk history, SHAP explanations, and analyst feedback.
Uses centralised settings instead of hardcoded paths.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import pandas as pd
import os
import joblib
import hashlib
import logging
from datetime import datetime

from src.api.config import settings
from src.api.security import require_role

logger = logging.getLogger("uba.analysis")

# =============================================================================
# OPTIONAL / HEAVY DEPENDENCIES (best-effort imports)
# =============================================================================
# Each of these pulls in optional third-party libs (shap, xgboost, torch,
# cryptography, pgmpy, ...). If any fails to import — e.g. `cryptography` is
# momentarily absent while a teammate installs it — we degrade the affected
# feature (its endpoint returns 503) instead of taking down the whole app.
# The names are set to None on failure and guarded at call sites.

try:
    from src.risk_engine.bayesian_network import bayesian_network
except Exception as e:  # pragma: no cover - environment dependent
    bayesian_network = None
    logger.warning("bayesian_network unavailable — risk-distribution disabled: %s", e)

try:
    from src.models.thresholding import adaptive_threshold, drift_detector
except Exception as e:
    adaptive_threshold = None
    drift_detector = None
    logger.warning("thresholding unavailable — drift/threshold degraded: %s", e)

try:
    from src.security.privacy import (
        pseudonymization,
        access_control,
        cryptographic_erasure,
    )
except Exception as e:
    pseudonymization = None
    access_control = None
    cryptographic_erasure = None
    logger.warning("privacy module unavailable (crypto?) — privacy features disabled: %s", e)

try:
    from src.deployment.operations import shadow_deployment, synthetic_generator
except Exception as e:
    shadow_deployment = None
    synthetic_generator = None
    logger.warning("deployment.operations unavailable — synthetic generator disabled: %s", e)

# SHAP explainer (best-effort import)
try:
    from src.models.explainability import SHAPExplainer
except Exception as e:
    SHAPExplainer = None
    logger.warning("SHAPExplainer unavailable — explainability disabled: %s", e)

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
        df = pd.read_csv(DATA_PATH, encoding="utf-8")
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
        df = pd.read_csv(DATA_PATH, encoding="utf-8")
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
        new_row.to_csv(feedback_path, mode="a", header=header, index=False, encoding="utf-8")
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
    if bayesian_network is None:
        raise HTTPException(
            status_code=503,
            detail="Bayesian risk engine is not available in this deployment.",
        )
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


# Drift/threshold columns produced by the risk pipeline in risk_report_users.csv.
USERS_REPORT_PATH = os.path.join(settings.RISK_OUTPUT_DIR, "risk_report_users.csv")


@router.get("/analysis/drift-status")
async def check_concept_drift():
    """
    Report concept-drift status derived from the risk pipeline's real output.

    Reads the ``is_drift`` / ``deviation_sigma`` / ``drift_explanation`` columns
    that the risk pipeline writes to ``risk_report_users.csv`` and summarises
    how many users are currently drifting. Returns a typed empty response
    (``drift_detected=False``, ``data_source="unavailable"``) if the file or the
    columns are missing — it never fabricates data and never 500s on missing
    input.
    """
    empty = {
        "status": "success",
        "data_source": "unavailable",
        "drift_detected": False,
        "users_total": 0,
        "users_in_drift": 0,
        "drift_ratio": 0.0,
        "max_deviation_sigma": 0.0,
        "top_drifting_users": [],
        "recommendation": "No drift report available. Run the risk pipeline to populate risk_report_users.csv.",
    }

    if not os.path.exists(USERS_REPORT_PATH):
        return empty

    try:
        df = pd.read_csv(USERS_REPORT_PATH, encoding="utf-8")
    except Exception as e:
        logger.warning("Could not read %s: %s", USERS_REPORT_PATH, e)
        return empty

    if df.empty or "is_drift" not in df.columns:
        return empty

    # Normalise the boolean-ish is_drift column.
    is_drift = df["is_drift"].astype(str).str.strip().str.lower().isin(
        {"true", "1", "yes"}
    )
    users_total = int(len(df))
    users_in_drift = int(is_drift.sum())

    sigma = pd.to_numeric(df.get("deviation_sigma", 0), errors="coerce").fillna(0.0)
    max_sigma = float(sigma.max()) if len(sigma) else 0.0

    drifting = df[is_drift].copy()
    drifting = drifting.assign(_sigma=pd.to_numeric(
        drifting.get("deviation_sigma", 0), errors="coerce"
    ).fillna(0.0)).sort_values("_sigma", ascending=False)

    top = []
    for _, row in drifting.head(10).iterrows():
        top.append({
            "user": str(row.get("user", "")),
            "total_risk_score": round(float(pd.to_numeric(row.get("total_risk_score", 0), errors="coerce") or 0), 2),
            "deviation_sigma": round(float(row.get("_sigma", 0)), 2),
            "explanation": str(row.get("drift_explanation", "")) if pd.notna(row.get("drift_explanation", "")) else "",
        })

    return {
        "status": "success",
        "data_source": "risk_report_users.csv",
        "drift_detected": users_in_drift > 0,
        "users_total": users_total,
        "users_in_drift": users_in_drift,
        "drift_ratio": round(users_in_drift / users_total, 4) if users_total else 0.0,
        "max_deviation_sigma": round(max_sigma, 2),
        "top_drifting_users": top,
        "recommendation": (
            f"{users_in_drift} of {users_total} users are drifting from baseline. "
            "Review the top drifting users and consider retraining."
            if users_in_drift else
            "No users are currently drifting from baseline."
        ),
    }


@router.post("/analysis/update-threshold", dependencies=[Depends(require_role("Admin", "Analyst"))])
async def update_threshold(method: str = "percentile"):
    """
    Recompute an adaptive anomaly threshold over the pipeline's real risk scores.

    Runs the adaptive-threshold algorithm over the ``total_risk_score`` column
    of ``risk_report_users.csv`` (the risk pipeline's real output) rather than
    fabricated numbers. Requires Admin/Analyst (demo RBAC).

    Methods: percentile, evt, cost, iqr, std.

    If the thresholding module or the report is unavailable, returns a clearly
    labelled ``data_source`` so the caller never mistakes a fallback for a real
    computation.
    """
    if adaptive_threshold is None:
        raise HTTPException(
            status_code=503,
            detail="Adaptive thresholding module is not available in this deployment.",
        )

    scores = None
    data_source = "unavailable"
    if os.path.exists(USERS_REPORT_PATH):
        try:
            df = pd.read_csv(USERS_REPORT_PATH, encoding="utf-8")
            if "total_risk_score" in df.columns and not df.empty:
                scores = pd.to_numeric(
                    df["total_risk_score"], errors="coerce"
                ).dropna().to_numpy()
                data_source = "risk_report_users.csv"
        except Exception as e:
            logger.warning("Could not read scores from %s: %s", USERS_REPORT_PATH, e)

    if scores is None or len(scores) == 0:
        raise HTTPException(
            status_code=404,
            detail="No risk scores available to compute a threshold. Run the risk pipeline first.",
        )

    try:
        result = adaptive_threshold.calculate_threshold(scores, method=method)
        return {
            "status": "success",
            "data_source": data_source,
            "sample_size": int(len(scores)),
            "threshold": result.threshold,
            "method": result.method,
            "confidence": result.confidence,
            "metadata": result.metadata,
        }
    except Exception as e:
        logger.exception("Threshold update failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthetic/generate", dependencies=[Depends(require_role("Admin", "Analyst"))])
async def generate_synthetic_data(
    scenario: str = "data_exfiltration",
    intensity: float = 1.0,
    n_samples: int = 100
):
    """
    Generate synthetic threat scenario data (clearly labelled as synthetic).

    Requires Admin/Analyst (demo RBAC). Returns 503 if the synthetic generator
    module is unavailable in this deployment.
    """
    if synthetic_generator is None:
        raise HTTPException(
            status_code=503,
            detail="Synthetic data generator is not available in this deployment.",
        )
    try:
        synthetic = synthetic_generator._create_synthetic_events(
            scenario=scenario,
            user_id="synthetic_user",
            intensity=intensity
        )

        return {
            "status": "success",
            "synthetic": True,
            "scenario": scenario,
            "event_count": len(synthetic),
            "events": synthetic.to_dict(orient='records') if len(synthetic) > 0 else []
        }

    except Exception as e:
        logger.exception("Synthetic data generation failed")
        raise HTTPException(status_code=500, detail=str(e))
