from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_BACKEND_ROOT / ".env", override=True)


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    minio_public_endpoint: str = os.getenv(
        "MINIO_PUBLIC_ENDPOINT",
        os.getenv("MINIO_ENDPOINT", "localhost:9000"),
    )
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./data/wafabail.db",
    )
    job_dispatcher: str = os.getenv("JOB_DISPATCHER", "local").strip().lower()
    local_job_concurrency: int = int(os.getenv("LOCAL_JOB_CONCURRENCY", "1"))
    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))
    scoring_policy_version: str = os.getenv("SCORING_POLICY_VERSION", "WFB-CREDIT-V1")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "wafabail-dossiers")
    minio_secure: bool = os.getenv("MINIO_SECURE", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    dossiers_store_path: Path = Path(
        os.getenv(
            "DOSSIERS_STORE_PATH",
            str(_BACKEND_ROOT / "data" / "dossiers.json"),
        )
    )
    storage_backend: str = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    files_dir: Path = Path(
        os.getenv(
            "FILES_DIR",
            str(_BACKEND_ROOT / "data" / "files"),
        )
    )
    kafka_enabled: bool = _flag("KAFKA_ENABLED", False)
    kafka_bootstrap_servers: str = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        "localhost:9094",
    )
    kafka_topic_dossiers: str = os.getenv(
        "KAFKA_TOPIC_DOSSIERS",
        "wafabail.dossiers.created",
    )
    kafka_topic_scoring: str = os.getenv(
        "KAFKA_TOPIC_SCORING",
        "wafabail.scoring.events",
    )
    rcc_ollama_url: str = os.getenv(
        "RCC_OLLAMA_URL",
        os.getenv("OLLAMA_URL", "https://ollama-lnhh4y-11434.svc-usw2.nicegpu.com"),
    ).rstrip("/")
    rcc_vision_model: str = os.getenv(
        "RCC_VISION_MODEL", "hf.co/unsloth/GLM-4.6V-Flash-GGUF:Q4_K_M"
    )
    rcc_ocr_model: str = os.getenv("RCC_OCR_MODEL", "glm-ocr:q8_0")
    rcc_verify_model: str = os.getenv("RCC_VERIFY_MODEL", "qwen3-vl:30b")
    rcc_mapper_model: str = os.getenv("RCC_MAPPER_MODEL", "qwen3.5:9b")
    rcc_copilot_model: str = os.getenv(
        "RCC_COPILOT_MODEL",
        os.getenv("RCC_MAPPER_MODEL", "qwen3.5:9b"),
    )
    rcc_adjudicator_model: str = os.getenv("RCC_ADJUDICATOR_MODEL", "gemma4:latest")
    rcc_use_glm_verification: bool = _flag("RCC_USE_GLM_VERIFICATION", True)
    rcc_use_reasoning_mapper: bool = _flag("RCC_USE_REASONING_MAPPER", True)
    rcc_use_adjudicator: bool = _flag("RCC_USE_ADJUDICATOR", True)
    rcc_request_timeout_seconds: int = int(os.getenv("RCC_REQUEST_TIMEOUT_SECONDS", "600"))
    rcc_keep_alive: str = os.getenv("RCC_KEEP_ALIVE", "20m")
    rcc_render_dpi: int = int(os.getenv("RCC_RENDER_DPI", "220"))
    rcc_extract_max_side: int = int(os.getenv("RCC_EXTRACT_MAX_SIDE", "2400"))
    rcc_max_pages: int = int(os.getenv("RCC_MAX_PAGES", "60"))
    analyse_job_ttl_minutes: int = int(os.getenv("ANALYSE_JOB_TTL_MINUTES", "180"))
    pvc_api_key: str = os.getenv("PVC_API_KEY", "").strip()
    tesseract_cmd: str = os.getenv("TESSERACT_CMD", "").strip()
    sector_data_enabled: bool = _flag("SECTOR_DATA_ENABLED", True)
    sector_data_auto_sync: bool = _flag(
        "SECTOR_AUTO_REFRESH",
        _flag("SECTOR_DATA_AUTO_SYNC", True),
    )
    sector_data_refresh_hours: int = int(
        os.getenv("SECTOR_REFRESH_INTERVAL_HOURS", os.getenv("SECTOR_DATA_REFRESH_HOURS", "24"))
    )
    sector_metadata_ttl_hours: int = int(os.getenv("SECTOR_METADATA_TTL_HOURS", "6"))
    sector_analysis_affects_scoring: bool = _flag("SECTOR_ANALYSIS_AFFECTS_SCORING", False)
    sector_data_provider: str = os.getenv(
        "SECTOR_PROVIDER", os.getenv("SECTOR_DATA_PROVIDER", "hcp_open_data")
    ).strip().lower()
    sector_data_request_timeout_seconds: int = int(
        os.getenv("SECTOR_DATA_REQUEST_TIMEOUT_SECONDS", "30")
    )
    sector_data_max_retries: int = int(os.getenv("SECTOR_DATA_MAX_RETRIES", "3"))
    sector_data_store_raw_files: bool = _flag("SECTOR_DATA_STORE_RAW_FILES", True)
    sector_data_max_xlsx_bytes: int = int(os.getenv("SECTOR_DATA_MAX_XLSX_BYTES", str(20 * 1024 * 1024)))
    hcp_ckan_base_url: str = os.getenv(
        "DATA_GOV_MA_CKAN_BASE",
        os.getenv("HCP_CKAN_BASE_URL", "https://data.gov.ma/data/api/3/action"),
    ).rstrip("/")

    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,"
            "http://localhost:5174,http://127.0.0.1:5174,"
            "http://localhost:5175,http://127.0.0.1:5175,"
            "http://localhost:8080,http://127.0.0.1:8080",
        ).split(",")
        if origin.strip()
    ]


settings = Settings()
