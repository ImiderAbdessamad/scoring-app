# Analyse sectorielle HCP — Wafabail scoring

## Architecture

HCP Open Data (CKAN) → provider `HcpCkanProvider` → téléchargement XLSX → parser → `sector_observations` SQLite → mapping entreprise → `SectorAnalysisService` → workspace + onglet « Analyse sectorielle ».

Le scoring officiel **n’est pas modifié**. `sectorOfficialScore` / `includedInFinalScore` restent nuls tant que `SECTOR_ANALYSIS_AFFECTS_SCORING=false` et qu’aucune policy n’est validée.

## Sources

Jeux V1 (IDs préférés, resource_id jamais hardcodé) :

- `data_12_29` VA annuelle prix courants
- `data_12_28` VA annuelle volume chaîné
- `data_12_41` VA trimestrielle CVS prix courants
- `data_12_40` VA trimestrielle CVS volume

API : `DATA_GOV_MA_CKAN_BASE` (défaut `https://data.gov.ma/data/api/3/action`). `success == true` obligatoire.

## Refresh / cache

- Lecture SQLite immédiate
- TTL métadonnées : `SECTOR_METADATA_TTL_HOURS` (6)
- Boucle : `SECTOR_REFRESH_INTERVAL_HOURS` (24) si `SECTOR_AUTO_REFRESH=true`
- Startup : tâche asyncio, **non bloquante**, pas d’Internet requis
- Échec HCP : observations précédentes conservées

## Mapping

Priorité : override manuel (`benchmarkSectorCode`) → exact → alias → mot-clé haute confiance → `UNMAPPED`. Pas de LLM.

## Nominal vs réel

VA entreprise ESG = nominale. Le gap est **nominal** vs HCP prix courants. La croissance réelle HCP est un indicateur de conjoncture, jamais soustraite à la croissance entreprise.

## API

- `GET /api/v1/sectors/sources/status`
- `POST /api/v1/sectors/refresh`
- `GET /api/v1/dossiers/{id}/sector-analysis?refresh=auto|false|force`
- `PUT /api/v1/dossiers/{id}/sector-mapping`

## Limitations

- HCP = macro, pas de pairs individuels
- pas d’historique portefeuille Wafabail
- pas d’OMPIC / DirectInfo
- mapping parfois à valider
- publication HCP avec retard
- score officiel non modifié
