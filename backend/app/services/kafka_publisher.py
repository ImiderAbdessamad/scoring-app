from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_producer = None


def _bootstrap() -> str:
    from app.core.config import settings

    return settings.kafka_bootstrap_servers


def _topic_dossiers() -> str:
    from app.core.config import settings

    return settings.kafka_topic_dossiers


def _topic_scoring() -> str:
    from app.core.config import settings

    return settings.kafka_topic_scoring


def get_producer():
    global _producer
    from app.core.config import settings

    if not settings.kafka_enabled:
        return None
    if _producer is not None:
        return _producer
    try:
        from kafka import KafkaProducer
    except ImportError:
        logger.warning("kafka-python non installé — publication Kafka désactivée")
        return None

    try:
        _producer = KafkaProducer(
            bootstrap_servers=_bootstrap().split(","),
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False, default=str).encode("utf-8"),
            key_serializer=lambda v: v.encode("utf-8") if v else None,
            acks="all",
            retries=3,
            request_timeout_ms=10000,
        )
        logger.info("Producteur Kafka prêt (%s)", _bootstrap())
    except Exception as exc:
        logger.warning("Kafka indisponible : %s", exc)
        _producer = None
    return _producer


def publish(topic: str, payload: dict[str, Any], *, key: str | None = None) -> bool:
    producer = get_producer()
    if producer is None:
        return False
    try:
        future = producer.send(topic, key=key or None, value=payload)
        future.get(timeout=10)
        producer.flush(timeout=5)
        logger.info("Événement Kafka publié — topic=%s key=%s event=%s", topic, key, payload.get("event"))
        return True
    except Exception as exc:
        logger.warning("Échec publication Kafka topic=%s : %s", topic, exc)
        return False


def publish_dossier_created(payload: dict[str, Any]) -> bool:
    dossier_id = str(payload.get("id", ""))
    body = {"event": "dossier.created", **payload}
    return publish(_topic_dossiers(), body, key=dossier_id or None)


def publish_scoring_event(
    event: str,
    *,
    job_id: str,
    dossier_id: str,
    **extra: Any,
) -> bool:
    payload = {
        "event": event,
        "job_id": job_id,
        "dossier_id": dossier_id,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **extra,
    }
    return publish(_topic_scoring(), payload, key=dossier_id)
