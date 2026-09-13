FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/worker ./worker

ENV KAFKA_BOOTSTRAP_SERVERS=kafka:29092
ENV KAFKA_TOPIC_DOSSIERS=wafabail.dossiers.created
ENV KAFKA_CONSUMER_GROUP=wafabail-dossier-worker

CMD ["python", "-u", "worker/dossier_worker.py"]
