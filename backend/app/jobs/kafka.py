from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class KafkaJobDispatcher:
    async def dispatch_analysis(self, job_id: str) -> None:
        from app.services import kafka_publisher

        kafka_publisher.publish_scoring_event(
            "scoring.job.dispatch",
            job_id=job_id,
            dossier_id="",
        )
