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
logger = logging.getLogger("dossier-worker")

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TOPIC = os.getenv("KAFKA_TOPIC_DOSSIERS", "wafabail.dossiers.created")
GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "wafabail-dossier-worker")

_running = True


def _stop(*_args):
    global _running
    _running = False


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
            logger.info("Worker connecté — bootstrap=%s topic=%s", BOOTSTRAP, TOPIC)
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
                logger.info(
                    "Traitement dossier %s — entreprise=%s fichiers=%s",
                    data.get("id"),
                    data.get("name"),
                    len(data.get("files") or []),
                )
        except Exception as exc:
            if _running:
                logger.warning("Boucle consumer : %s", exc)
                time.sleep(2)

    consumer.close()
    logger.info("Worker arrêté")
    return 0


if __name__ == "__main__":
    sys.exit(main())
