from fastapi import APIRouter

from app.schemas.dashboard import DashboardData
from app.services.dashboard_service import get_dashboard

router = APIRouter()


@router.get("/dashboard", response_model=DashboardData, summary="Tableau de bord scoring")
def dashboard() -> DashboardData:
    """KPIs, dossiers en file, alertes et file d'attente d'analyse."""
    return get_dashboard()
