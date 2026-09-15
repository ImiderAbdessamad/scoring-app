from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.services import minio_storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = cid
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        return response


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.core.config import settings
    from app.db.repositories import job_repository, scoring_policy_repository
    from app.db.session import init_database
    from app.domain.scoring_policy import default_policy, policy_as_dict

    try:
        init_database()
        policy = default_policy()
        scoring_policy_repository.ensure_default(
            settings.scoring_policy_version,
            policy.name,
            policy_as_dict(policy),
        )
        interrupted = job_repository.interrupt_running()
        if interrupted:
            logger.warning("%s job(s) RUNNING marqués INTERRUPTED au démarrage", interrupted)
    except Exception as exc:
        logger.warning("Initialisation SQLite : %s", exc)
    try:
        minio_storage.ensure_bucket()
        if settings.storage_backend == "minio":
            logger.info("MinIO prêt")
        else:
            logger.info("Mode local — fichiers dans %s", settings.files_dir)
    except Exception as exc:
        logger.warning("Stockage non initialisé au démarrage : %s", exc)
    if not settings.kafka_enabled:
        logger.info("Kafka désactivé (KAFKA_ENABLED=false)")
    if settings.sector_data_enabled and settings.sector_data_auto_sync and not os.getenv("PYTEST_CURRENT_TEST"):
        import asyncio

        from app.services.sector_sync_service import sector_sync_loop

        asyncio.create_task(sector_sync_loop())
    yield


app = FastAPI(
    title="Wafabail Smart Dashboard API",
    version="0.2.0",
    description="API crédit-bail — dashboard & dossiers",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
@app.get("/health/live")
def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready():
    from app.core.config import settings
    from app.db.session import sync_engine
    from sqlalchemy import text

    db_status = "ok"
    try:
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    minio_status = "ok"
    try:
        minio_storage.ensure_bucket()
    except Exception:
        minio_status = "error" if settings.storage_backend == "minio" else "local"
    kafka_status = "ok" if settings.kafka_enabled else "disabled"
    ready = db_status == "ok"
    return {
        "status": "ready" if ready else "degraded",
        "database": db_status,
        "minio": minio_status,
        "extractor": "ok",
        "kafka": kafka_status,
    }
