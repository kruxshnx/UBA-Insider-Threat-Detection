from fastapi import APIRouter, Query
from src.api.services.data_loader import data_loader
from src.api.schemas.responses import UserTimeline

router = APIRouter()


@router.get("/users/{user_id}/timeline", response_model=UserTimeline)
def get_user_timeline(
    user_id: str,
    limit: int = Query(200, ge=1, le=2000, description="Maximum events per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Get the full event timeline for a specific user.

    Returns chronological events with anomaly scores, risk scores,
    and anomaly flags for forensic investigation.
    Supports pagination via `limit` and `offset`.
    """
    return data_loader.get_user_timeline(user_id, limit=limit, offset=offset)
