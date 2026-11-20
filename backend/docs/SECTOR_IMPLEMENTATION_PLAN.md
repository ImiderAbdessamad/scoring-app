# Plan — Analyse sectorielle HCP (Wafabail scoring)

## Runtime actif (une seule copie)

| Rôle | Fichier actif |
|---|---|
| FastAPI | `backend/app/main.py` |
| Router API | `backend/app/api/v1/router.py` |
| Workspace | `backend/app/services/workspace_builder.py` |
| Pipeline V6 | `backend/app/services/scoring_lab_pipeline.py` |
| Mapper V6 | `backend/app/services/v6_result_mapper.py` |
| Analyse UI | `frontend/src/features/analyse/AnalysePage.tsx` |
| Onglets | `frontend/src/features/analyse/components/AnalyseTabs.tsx` |
| Analyse sectorielle | `frontend/src/features/analyse/components/tabs/SectorAnalysisTab.tsx` |
| Comportement | `frontend/src/features/analyse/components/tabs/ComportementTab.tsx` |
| Types | `frontend/src/types/analyse.ts` |
| SQLite sectorielle | `backend/app/db/models/sector_data.py` + Alembic `0002_sector.py` |

Ne pas toucher les copies RCC / V4 / V5 hors de ce runtime.

## Déjà en place

- Provider CKAN `hcp_ckan.py` (`success == true`, XLSX, SHA256)
- Parser `hcp_parser.py` (en-têtes dynamiques)
- Sync cache + boucle `sector_sync_service.py`
- Mapping HCP labels réels (`mapping.py`)
- Service d’analyse + snapshot SQLite
- VA / EBE dans `_YEAR_SERIES_FIELDS`
- `score_axe3_sectoriel` sans fallback médianes
- Onglets relabelés (IDs internes inchangés)
- Graphiques SVG internes (pas Recharts — absent du `package.json`)

## Écarts à combler dans ce lot

- Endpoints spec : `POST /sectors/refresh`, `GET /sectors/sources/status`, `PUT .../sector-mapping`, `refresh=auto|false|force`
- Alias config spec (`DATA_GOV_MA_CKAN_BASE`, TTL 6h, `SECTOR_ANALYSIS_AFFECTS_SCORING`)
- Override mapping manuel prioritaire
- Statuts `UNMAPPED` / `NO_DATA` / `STALE` + insights déterministes
- `synthese_builder` : plus de `DEFAULT_SECTOR_MEDIANS`
- Client frontend `services/sectors.ts`
- Docs `docs/SECTOR_ANALYSIS.md`, rapport, diagnostics
- Tests CKAN / mapping / refresh / frontend

## Fichiers à modifier / créer

Voir `SECTOR_IMPLEMENTATION_REPORT.md` en fin de lot.

## Schéma SQLite (existant, conservé)

`sector_data_sources`, `sector_datasets`, `sector_observations`, `sector_sync_runs`, `sector_mappings`, `sector_analysis_snapshots`

(Noms légèrement différents du brief ; pas de migration destructive.)

## Endpoints prévus

- `GET /api/v1/sectors/sources/status`
- `POST /api/v1/sectors/refresh`
- `GET /api/v1/dossiers/{id}/sector-analysis?refresh=auto|false|force`
- `PUT /api/v1/dossiers/{id}/sector-mapping`
- Conservés : `/sector-data/status`, `/sector-data/sync`

## Dépendances

`httpx`, `openpyxl`, SQLite SQLAlchemy — déjà présentes. Pas de Recharts (SVG existants).
