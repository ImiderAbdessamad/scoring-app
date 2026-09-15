# Architecture données sectorielles HCP

```
HCP Open Data (CKAN)
      ↓
HcpCkanProvider (httpx, timeout, retry 1/2/4s, hôtes allowlist)
      ↓
Validation schéma XLSX (HcpWorkbookParser)
      ↓
Cache versionné (SHA256 + fichier brut MinIO/local)
      ↓
SQLite : sources, datasets, observations, sync_runs, mappings, snapshots
      ↓
SectorMappingService (déterministe, jamais LLM)
      ↓
Données entreprise V6 (usable_value uniquement)
      ↓
SectorAnalysisService (croissance nominale, indice 100, VA réelle séparée)
      ↓
Workspace UI « Analyse sectorielle »
      ↓
Décision humaine — score sectoriel NOT_CALIBRATED (hors note finale)
```

## Sync

- Au démarrage si `SECTOR_DATA_AUTO_SYNC=true` (sauf pytest)
- Puis toutes les `SECTOR_DATA_REFRESH_HOURS` (24 h)
- À la demande : `POST /api/v1/sector-data/sync`
- Une analyse dossier ne télécharge jamais HCP de façon bloquante

## Fraîcheur

FRESH / STALE / VERY_STALE / UNAVAILABLE selon dernier sync réussi, pas seulement l’année d’observation.
