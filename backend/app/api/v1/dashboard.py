from fastapi import APIRouter

from app.schemas.dashboard import DashboardData
from app.services.dashboard_service import get_dashboard

router = APIRouter()


@router.get("/dashboard", response_model=DashboardData)
def dashboard() -> DashboardData:
    return get_dashboard()
