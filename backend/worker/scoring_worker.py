from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("scoring-worker")

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TOPIC = os.getenv("KAFKA_TOPIC_SCORING", "wafabail.scoring.events")
GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "wafabail-scoring-worker")

_running = True


def _stop(*_args):
    global _running
    _running = False


def _handle(event: dict) -> None:
    kind = event.get("event")
    dossier_id = event.get("dossier_id")
    job_id = event.get("job_id")
    if kind == "scoring.job.queued":
        logger.info(
            "Scoring queued — dossier=%s job=%s file=%s company=%s",
            dossier_id,
            job_id,
            event.get("filename"),
            event.get("company"),
        )
        return
    if kind == "scoring.job.started":
        logger.info("Scoring started — dossier=%s job=%s", dossier_id, job_id)
        return
    if kind == "scoring.job.completed":
        logger.info(
            "Scoring completed — dossier=%s job=%s score=%s classe=%s completeness=%s%%",
            dossier_id,
            job_id,
            event.get("score"),
            event.get("classe"),
            event.get("completeness_pct"),
        )
        return
    if kind == "scoring.job.failed":
        logger.warning(
            "Scoring failed — dossier=%s job=%s error=%s",
            dossier_id,
            job_id,
            event.get("error"),
        )
        return
    logger.info("Événement scoring ignoré — %s dossier=%s", kind, dossier_id)


def main() -> int:
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    from kafka import KafkaConsumer

    consumer = None
    while _running and consumer is None:
        try:
            consumer = KafkaConsumer(
                TOPIC,
                bootstrap_servers=BOOTSTRAP.split(","),
                group_id=GROUP,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda b: json.loads(b.decode("utf-8")),
                consumer_timeout_ms=1000,
            )
            logger.info("Worker scoring connecté — bootstrap=%s topic=%s", BOOTSTRAP, TOPIC)
        except Exception as exc:
            logger.warning("Connexion Kafka échouée : %s — retry 3s", exc)
            time.sleep(3)

    if consumer is None:
        return 1

    while _running:
        try:
            for msg in consumer:
                if not _running:
                    break
                data = msg.value or {}
                if not isinstance(data, dict):
                    logger.warning("Message scoring non JSON objet — partition=%s offset=%s", msg.partition, msg.offset)
                    continue
                try:
                    _handle(data)
                except Exception:
                    logger.exception("Traitement scoring échoué — dossier=%s", data.get("dossier_id"))
        except Exception as exc:
            if _running:
                logger.warning("Boucle consumer : %s", exc)
                time.sleep(2)

    consumer.close()
    logger.info("Worker scoring arrêté")
    return 0


if __name__ == "__main__":
    sys.exit(main())
