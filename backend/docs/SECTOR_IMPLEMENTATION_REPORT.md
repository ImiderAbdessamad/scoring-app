# Rapport d’implémentation — analyse sectorielle

## Runtime

Copie unique : `WFB/backend` + `WFB/frontend`. Plan : `SECTOR_IMPLEMENTATION_PLAN.md`.

Tests **avant** modification : 42 passed (`test_sector_analysis`, `test_synthese_builder`, `test_wfb_finalisation`).

## Fichiers créés

- `backend/app/api/v1/sectors.py`
- `backend/app/sector/parsers/hcp_xlsx.py`
- `backend/app/sector/providers/hcp_open_data.py`
- `backend/app/services/sector_refresh_service.py`
- `backend/app/services/sector_data_service.py`
- `frontend/src/services/sectors.ts`
- `docs/SECTOR_ANALYSIS.md`
- `SECTOR_IMPLEMENTATION_PLAN.md`
- `SECTOR_DATA_DIAGNOSTICS.json`

## Fichiers modifiés (principaux)

- `config.py` — alias env spec (CKAN, TTL, auto-refresh, flag scoring)
- `hcp_ckan.py` — `success==true`, fallback `package_search`, Protocol spec
- `mapping.py` — override manuel prioritaire
- `sector_analysis_service.py` — UNMAPPED/NO_DATA, insights, momentum, ratios nuls
- `synthese_builder.py` — plus de `DEFAULT_SECTOR_MEDIANS`
- `AnalyseTabs` déjà relabelés ; `SectorAnalysisTab` + `ComportementTab`
- Alembic `0002_sector.py` (existant, conservé)

## Endpoints

- `GET /api/v1/sectors/sources/status` → 200 `HCP_OPEN_DATA`
- `POST /api/v1/sectors/refresh`
- `GET /api/v1/dossiers/{id}/sector-analysis?refresh=auto|false|force`
- `PUT /api/v1/dossiers/{id}/sector-mapping`

## Datasets HCP

`data_12_29`, `data_12_28`, `data_12_41`, `data_12_40` — voir `SECTOR_DATA_DIAGNOSTICS.json` (valeurs SQLite locales).

## Mapping

Labels HCP réels (ex. Construction, Commerce de gros et de détail…). Override `benchmarkSectorCode` prioritaire.

## Tests

- Backend sectoriel : 26 passed
- Synthèse + finalisation : passed
- Frontend vitest `sector-analysis.test.ts` : 8 passed
- Smoke : `GET /sectors/sources/status` 200

## Limitations restantes

- Recharts non ajouté (SVG existants)
- Noms de tables SQLite historiques (`sector_data_sources`, `sector_sync_runs`) non renommés
- Score officiel toujours `NOT_CALIBRATED` / non injecté dans le score final
- OMPIC / APSF / pairs : non implémentés (V1 HCP seul)
