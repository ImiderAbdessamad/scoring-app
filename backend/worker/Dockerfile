# Non utilisé par docker-compose : les workers partagent l'image API.
# Worker Kafka autonome (logs d'événements uniquement).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN pip install --no-cache-dir kafka-python

COPY backend/worker /app/worker

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD ["python", "-u", "worker/dossier_worker.py"]
