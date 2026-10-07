from fastapi import APIRouter, Depends

from app.api.v1 import analyse, dashboard, dossiers, partners, rcc, sector_data, sectors
from app.core.security import get_current_user, get_scoring_user

# Application Scoring : Keycloak, client scoring-wb, rôle SCORING_USER.
scoring_auth = [Depends(get_scoring_user)]

api_router = APIRouter()
api_router.include_router(dashboard.router, tags=["dashboard"], dependencies=scoring_auth)
api_router.include_router(dossiers.router, tags=["dossiers"], dependencies=scoring_auth)
api_router.include_router(analyse.router, dependencies=scoring_auth)
# Partenaire PVC (pv-manager) : clé API, hors Keycloak.
api_router.include_router(partners.router)
api_router.include_router(sector_data.router, dependencies=scoring_auth)
api_router.include_router(sectors.router, dependencies=scoring_auth)
api_router.include_router(sectors.dossier_router, dependencies=scoring_auth)
api_router.include_router(sector_data.dossier_sector_router, dependencies=scoring_auth)
# Application RCC : Keycloak, client rcc-wb, rôle RCC_USER.
api_router.include_router(rcc.public_router)
api_router.include_router(rcc.auth_router, dependencies=[Depends(get_current_user)])
api_router.include_router(rcc.router, dependencies=[Depends(get_current_user)])
