# Architecture après finalisation V1 (SQLite / local)

Flux canonique :

DOCUMENT → OBSERVED → VALIDATION → USABLE → RATIOS → QUALITY GATE FINANCIER
→ PARTIAL / FINAL SCORING → BAM + INCIDENTS + SECTOR + DOCUMENTS
→ DECISION ELIGIBILITY → HUMAN DECISION → IMMUTABLE AUDIT

```
React
  → FastAPI
       → SQLite (SQLAlchemy + Alembic)
       → MinIO / disque local (fichiers)
       → V6 + Quality Gate + Ratio + Scoring + DecisionEligibility + SectorEngine
       → JobDispatcher
            LocalJobDispatcher (défaut)
            KafkaJobDispatcher (optionnel)
```

Les jobs d’analyse ne stockent plus de `pdf_bytes`. Références MinIO uniquement.

SSE = overlay mémoire. État canonique du job = SQLite.

## Tables SQLite

dossiers, documents, document_versions, analysis_jobs, analysis_runs,
decision_events, memos, scoring_policies, sector_benchmarks,
bam_assessments, incident_assessments

## Endpoints ajoutés / modifiés

- GET /health/live
- GET /health/ready
- POST /dossiers/{id}/approve|reserve|reject (body reason/comment, 409 DECISION_NOT_ELIGIBLE)
- GET /dossiers/{id}/decision-history
- GET /dossiers/{id}/decision-eligibility
- PUT /dossiers/{id}/risk-checks/bam|incidents
- POST/GET /dossiers/{id}/memos + sign
- GET /dossiers/{id}/analyses/{run_id}/fields

## Limitations

SQLite = pilote mono-instance, faible concurrence. Production multi-instance : PostgreSQL.
LocalJobDispatcher = Semaphore in-process, perdu au redémarrage (jobs RUNNING → INTERRUPTED).

## Démarrage

```
cd backend
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

cd frontend
npm install
npm run dev
```
