from fastapi import APIRouter
from src.api.services.data_loader import data_loader
from src.api.schemas.responses import SystemStats, DashboardSummary

router = APIRouter()


@router.get("/stats", response_model=SystemStats)
def get_stats():
    """
    Return aggregate system statistics.

    Includes total users, high-risk user count, total events,
    high-risk event count, average risk score, and the top-threat user.
    """
    return data_loader.get_system_stats()


@router.get("/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary():
    """
    Combined dashboard payload in a single request.

    Returns system stats, top 5 riskiest users, 5 most recent alerts,
    and ML model health — all in one call to reduce frontend latency.
    """
    return data_loader.get_dashboard_summary()
