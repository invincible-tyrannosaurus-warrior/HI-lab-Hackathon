from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from backend.models.cohort_signal import CohortSignal
from backend.schemas.common import dumps_json_list, generate_prefixed_id, utc_now
from backend.schemas.signal import CohortSignalCreate, CohortSignalStoredResponse

logger = logging.getLogger(__name__)


def store_cohort_signal(db: Session, payload: CohortSignalCreate) -> CohortSignalStoredResponse:
    signal = CohortSignal(
        signal_id=generate_prefixed_id("sig"),
        tested_deck_id=payload.tested_deck_id,
        related_knowledge_ids_json=dumps_json_list(payload.related_knowledge_ids),
        weak_topics_json=dumps_json_list(payload.weak_topics),
        repeated_confusion_points_json=dumps_json_list(payload.repeated_confusion_points),
        misconception_clusters_json=dumps_json_list(payload.misconception_clusters),
        evidence_refs_json=dumps_json_list(payload.evidence_refs),
        created_at=utc_now(),
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    logger.info("signal write-in success: signal_id=%s deck_id=%s", signal.signal_id, signal.tested_deck_id)
    return CohortSignalStoredResponse(signal_id=signal.signal_id, status="stored")
