from fastapi import APIRouter, Query
from typing import List
from src.api.services.data_loader import data_loader
from src.api.schemas.responses import RiskEvent

router = APIRouter()


@router.get("/events/risk", response_model=List[RiskEvent])
def get_risky_events(
    limit: int = Query(100, ge=1, le=1000, description="Maximum events to return"),
    min_score: float = Query(0.0, ge=0, description="Minimum risk score filter"),
):
    """
    Return risk-scored events from the risk pipeline, sorted by risk score
    descending.

    Surfaces the pipeline's real behavioral columns (file_copy_count, usb_count,
    removable_media_count, after_hours_ratio, delete_count, event_count) plus
    explanation / mitre_tactic / should_alert / alert_severity when present.
    Missing columns come back as null rather than a fabricated placeholder.

    Use `min_score` to filter out low-risk noise (e.g. `min_score=50`
    returns only events above the high-risk threshold). Returns an empty list
    (not a 500) when the pipeline output is missing.
    """
    return data_loader.get_events_risk_data(limit=limit, min_score=min_score)
