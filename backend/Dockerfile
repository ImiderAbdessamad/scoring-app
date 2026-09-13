FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TESSERACT_CMD=/usr/bin/tesseract \
    WFB_V6_EXTRACTOR=/app/financial_pdf_extractor-V6_corrected.py

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        tesseract-ocr \
        tesseract-ocr-fra \
        tesseract-ocr-eng \
        libglib2.0-0 \
        libgomp1 \
        libgl1 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/* \
    && tesseract --list-langs

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/app /app/app
COPY backend/worker /app/worker
COPY financial_pdf_extractor-V6_corrected.py /app/financial_pdf_extractor-V6_corrected.py

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data /data/files \
    && chown -R appuser:appuser /app /data

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=25s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Un seul process : le job store d'analyse est en mémoire.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
