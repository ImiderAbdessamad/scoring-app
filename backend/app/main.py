from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.services import minio_storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.core.config import settings

    try:
        minio_storage.ensure_bucket()
        if settings.storage_backend == "minio":
            logger.info("MinIO prêt")
        else:
            logger.info("Mode local — fichiers dans %s (Docker/MinIO/Kafka désactivés)", settings.files_dir)
    except Exception as exc:
        logger.warning("Stockage non initialisé au démarrage : %s", exc)
    if not settings.kafka_enabled:
        logger.info("Kafka désactivé (KAFKA_ENABLED=false)")
    yield


app = FastAPI(
    title="Wafabail Smart Dashboard API",
    version="0.1.0",
    description="API crédit-bail — dashboard & dossiers (MVP)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health():
    from app.core.config import settings

    return {
        "status": "ok",
        "storage": settings.storage_backend,
        "kafka": settings.kafka_enabled,
    }
