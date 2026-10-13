"""Enregistrement des dossiers RCC dans la base SQLite (tables rcc_dossiers / rcc_audit_events).

Le service RCC garde ses dossiers en mémoire pour la rapidité ; ce module les écrit à chaque
modification et les recharge au démarrage, pour qu'ils survivent aux redémarrages de l'API.
Une erreur d'écriture est journalisée sans faire échouer la requête de l'analyste.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import delete, select

from app.db.models.rcc import RccAuditEventModel, RccDossierModel, RccHiddenScoringModel
from app.db.session import session_scope, sync_engine

logger = logging.getLogger(__name__)

_tables_ready = False


def _ensure_tables() -> None:
    """Crée les tables RCC si besoin (l'API le fait déjà au démarrage via init_database)."""
    global _tables_ready
    if _tables_ready:
        return
    RccDossierModel.__table__.create(bind=sync_engine, checkfirst=True)
    RccAuditEventModel.__table__.create(bind=sync_engine, checkfirst=True)
    RccHiddenScoringModel.__table__.create(bind=sync_engine, checkfirst=True)
    _tables_ready = True


def load_all() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Dossiers (dict) et évènements d'audit (dans l'ordre chronologique d'écriture)."""
    try:
        _ensure_tables()
        with session_scope() as session:
            dossiers = [json.loads(row.payload_json) for row in session.scalars(select(RccDossierModel)).all()]
            audit = [
                json.loads(row.payload_json)
                for row in session.scalars(select(RccAuditEventModel).order_by(RccAuditEventModel.id)).all()
            ]
        return dossiers, audit
    except Exception:
        logger.exception("Chargement des dossiers RCC impossible : démarrage avec une liste vide.")
        return [], []


def save_dossier(payload: dict[str, Any]) -> None:
    try:
        _ensure_tables()
        with session_scope() as session:
            row = session.get(RccDossierModel, payload["id"]) or RccDossierModel(id=payload["id"])
            row.job_id = payload.get("job_id")
            row.origin = payload.get("origin") or "rcc"
            row.created_at = payload.get("created_at") or ""
            row.updated_at = payload.get("updated_at") or ""
            row.payload_json = json.dumps(payload, ensure_ascii=False, default=str)
            session.add(row)
            session.commit()
    except Exception:
        logger.exception("Enregistrement du dossier RCC %s impossible.", payload.get("id"))


def delete_dossier(dossier_id: str) -> None:
    try:
        _ensure_tables()
        with session_scope() as session:
            session.execute(delete(RccDossierModel).where(RccDossierModel.id == dossier_id))
            session.commit()
    except Exception:
        logger.exception("Suppression du dossier RCC %s impossible.", dossier_id)


def add_audit(event: dict[str, Any]) -> None:
    try:
        _ensure_tables()
        with session_scope() as session:
            session.add(
                RccAuditEventModel(
                    dossier_id=str(event.get("dossier_id") or ""),
                    timestamp=str(event.get("timestamp") or ""),
                    payload_json=json.dumps(event, ensure_ascii=False, default=str),
                )
            )
            session.commit()
    except Exception:
        logger.exception("Enregistrement de l'audit RCC impossible.")


def load_hidden_scoring() -> set[str]:
    try:
        _ensure_tables()
        with session_scope() as session:
            return set(session.scalars(select(RccHiddenScoringModel.dossier_id)).all())
    except Exception:
        logger.exception("Chargement des dossiers masqués impossible.")
        return set()


def hide_scoring(dossier_id: str, actor: str, timestamp: str) -> None:
    try:
        _ensure_tables()
        with session_scope() as session:
            if session.get(RccHiddenScoringModel, dossier_id) is None:
                session.add(RccHiddenScoringModel(dossier_id=dossier_id, hidden_by=actor, hidden_at=timestamp))
                session.commit()
    except Exception:
        logger.exception("Masquage du dossier %s impossible.", dossier_id)
