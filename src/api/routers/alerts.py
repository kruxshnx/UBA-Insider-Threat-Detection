from fastapi import APIRouter, Query
from typing import Optional
from src.api.services.data_loader import data_loader
from src.api.schemas.responses import AlertsResponse

router = APIRouter()


@router.get("/alerts", response_model=AlertsResponse)
def get_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: Critical, High, Medium"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    status: Optional[str] = Query(None, description="Filter by status: open, closed, investigating"),
    limit: int = Query(50, ge=1, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Get security alerts with optional filtering and pagination.

    Alerts are generated from high-risk events when no dedicated
    alerts file exists. Supports filtering by severity, user, and status.
    """
    return data_loader.get_alerts(
        severity=severity,
        user_id=user_id,
        status=status,
        limit=limit,
        offset=offset,
    )
