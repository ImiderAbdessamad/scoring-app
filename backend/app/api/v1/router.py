from fastapi import APIRouter, Depends

from app.api.v1 import analyse, dashboard, dossiers, partners, rcc, sector_data, sectors
from app.core.security import get_current_user

api_router = APIRouter()
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(dossiers.router, tags=["dossiers"])
api_router.include_router(analyse.router)
api_router.include_router(partners.router)
api_router.include_router(sector_data.router)
api_router.include_router(sectors.router)
api_router.include_router(sectors.dossier_router)
api_router.include_router(sector_data.dossier_sector_router)
api_router.include_router(rcc.public_router)
api_router.include_router(rcc.auth_router, dependencies=[Depends(get_current_user)])
api_router.include_router(rcc.router, dependencies=[Depends(get_current_user)])
