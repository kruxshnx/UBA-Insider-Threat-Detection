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
    Return risk-scored events, sorted by risk score descending.

    Use `min_score` to filter out low-risk noise (e.g. `min_score=50`
    returns only events above the high-risk threshold).
    """
    events = data_loader.get_events_risk_data(limit=limit, min_score=min_score)

    for e in events:
        e.setdefault("activity", "Unknown Activity")
    return events
