"""Configuration extraite pour le moteur v10 et l'API scoring."""
from __future__ import annotations

from app.core.config import settings

RCC_OLLAMA_URL = settings.rcc_ollama_url
RCC_VISION_MODEL = settings.rcc_vision_model
RCC_OCR_MODEL = settings.rcc_ocr_model
RCC_VERIFY_MODEL = settings.rcc_verify_model
RCC_MAPPER_MODEL = settings.rcc_mapper_model
RCC_COPILOT_MODEL = settings.rcc_copilot_model
RCC_ADJUDICATOR_MODEL = settings.rcc_adjudicator_model
RCC_USE_GLM_VERIFICATION = settings.rcc_use_glm_verification
RCC_USE_REASONING_MAPPER = settings.rcc_use_reasoning_mapper
RCC_USE_ADJUDICATOR = settings.rcc_use_adjudicator
RCC_REQUEST_TIMEOUT_SECONDS = settings.rcc_request_timeout_seconds
RCC_KEEP_ALIVE = settings.rcc_keep_alive
RCC_RENDER_DPI = settings.rcc_render_dpi
RCC_EXTRACT_MAX_SIDE = settings.rcc_extract_max_side
DIRECT_FINANCIAL_JOB_TTL_MINUTES = settings.analyse_job_ttl_minutes
DIRECT_FINANCIAL_MAX_PAGES = settings.rcc_max_pages
