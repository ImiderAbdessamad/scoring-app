# ACTIVE_RUNTIME_MAP — WFB (audit PHASE A)

Date : 2026-09-15  
Baseline tests : `backend/tests` → **33 passed** (pytest, 1 warning Starlette TestClient).

Le dépôt n’utilise **pas** `app/api/routes/`. Les routers actifs sont sous `app/api/v1/`.

## Point d’entrée

```
backend/app/main.py
  -> app/api/v1/router.py
       -> app/api/v1/dashboard.py
       -> app/api/v1/dossiers.py
       -> app/api/v1/analyse.py
       -> app/api/v1/partners.py
```

Config runtime : `app/core/config.py` (`Settings` + `.env`).  
Alias extracteur : `app/config.py` (réexporte `settings` pour V6 / Ollama).

## Analyse (chemin réel)

```
app/api/v1/analyse.py
    -> dossier_store (JSON, façade à migrer)
    -> analyse_job_store (mémoire + pdf_bytes — à retirer)
    -> scoring_lab_pipeline.run_scoring_job
        -> v6_extractor_bridge.run_v6_from_bytes
            -> financial_pdf_extractor-V6_corrected.py (racine WFB)
        -> v6_result_mapper.map_fields / identity / controls
        -> quality_gate.evaluate_quality
        -> ratio_engine / scoring_engine
        -> workspace_builder.build_workspace
    -> kafka_publisher (no-op si KAFKA_ENABLED=false)
```

`ocr_lab_core_v10.py` est encore importé par `scoring_lab_pipeline.py` (helpers parse_amount / client Ollama / ancien chemin PDF).  
**Extracteur liasses actif = V6**, pas v10.

## Dossiers

```
app/api/v1/dossiers.py
    -> dossier_service
        -> dossier_store (dossiers.json)
        -> minio_storage (ou disque local)
        -> kafka_publisher
```

## Config extracteur V6

`WFB_V6_EXTRACTOR` / chemin relatif racine WFB : `financial_pdf_extractor-V6_corrected.py`  
(`v6_extractor_bridge.py`).

## Tests existants (runtime)

- `tests/test_quality_gate.py`
- `tests/test_v6_mapper.py`
- `tests/test_workspace_stale.py`
- `tests/test_synthese_builder.py`
- `tests/test_excel_years_identity.py`
- `tests/test_pvc_partner_api.py`
- `tests/test_copilot_brief.py`
- `tests/test_identity_extract.py`

## Fichiers NON édités (hors graphe import runtime)

Copies ChatGPT / suffixes `(1)`, pipelines V4/V5, mappers morts : aucun fichier de ce type n’est importé par `main.py`.

## Frontend actif

`frontend/src/features/analyse/*`, `services/api/{client,dossiers,analyse}.ts`, wizard `features/dossiers/create/*`.
