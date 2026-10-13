"""Tables RCC : dossiers et piste d'audit, dans la même base que les dossiers scoring."""
from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RccDossierModel(Base):
    __tablename__ = "rcc_dossiers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    origin: Mapped[str] = mapped_column(String(16), default="rcc")
    # Dossier complet (extraction, corrections, n° tiers, envoi Ekip…) sérialisé en JSON.
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(40), default="")
    updated_at: Mapped[str] = mapped_column(String(40), default="")


class RccAuditEventModel(Base):
    __tablename__ = "rcc_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dossier_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[str] = mapped_column(String(40), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")


class RccHiddenScoringModel(Base):
    """Dossiers Étude de risque (scoring) masqués dans la liste RCC ; ils restent intacts côté scoring."""

    __tablename__ = "rcc_hidden_scoring"

    dossier_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hidden_by: Mapped[str] = mapped_column(String(128), default="")
    hidden_at: Mapped[str] = mapped_column(String(40), default="")
