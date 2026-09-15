from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.utcnow()


class DossierModel(Base):
    __tablename__ = "dossiers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(512), default="")
    ice: Mapped[str] = mapped_column(String(32), default="")
    identifiant_fiscal: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rc: Mapped[str] = mapped_column(String(64), default="")
    sector_raw: Mapped[str | None] = mapped_column(String(256), nullable=True)
    sector_normalized: Mapped[str | None] = mapped_column(String(128), nullable=True)
    benchmark_sector_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    duration: Mapped[int] = mapped_column(Integer, default=0)
    nature: Mapped[str] = mapped_column(String(32), default="")
    nature_bien: Mapped[str] = mapped_column(String(256), default="")
    etat: Mapped[str] = mapped_column(String(32), default="")
    fournisseur: Mapped[str] = mapped_column(String(256), default="")
    apport: Mapped[float] = mapped_column(Float, default=0)
    valeur_bien: Mapped[float] = mapped_column(Float, default=0)
    valeur_ht: Mapped[float] = mapped_column(Float, default=0)
    valeur_ttc: Mapped[float] = mapped_column(Float, default=0)
    proforma_reference: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    analyse_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_analysis_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    documents: Mapped[list["DocumentModel"]] = relationship(back_populates="dossier")


class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dossier_id: Mapped[str] = mapped_column(ForeignKey("dossiers.id"), index=True)
    name: Mapped[str] = mapped_column(String(512))
    object_key: Mapped[str] = mapped_column(String(1024))
    category: Mapped[str] = mapped_column(String(64), default="entreprise")
    mime_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    dossier: Mapped[DossierModel] = relationship(back_populates="documents")


class DocumentVersionModel(Base):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    object_key: Mapped[str] = mapped_column(String(1024))
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class AnalysisJobModel(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dossier_id: Mapped[str] = mapped_column(ForeignKey("dossiers.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[str] = mapped_column(String(64), default="queued")
    current_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pages_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pages_financial: Mapped[int] = mapped_column(Integer, default=0)
    pages_skipped: Mapped[int] = mapped_column(Integer, default=0)
    pages_failed: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatcher: Mapped[str] = mapped_column(String(32), default="local")
    filename: Mapped[str] = mapped_column(String(512), default="document.pdf")
    documents_json: Mapped[str] = mapped_column(Text, default="{}")
    analysis_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class AnalysisRunModel(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dossier_id: Mapped[str] = mapped_column(ForeignKey("dossiers.id"), index=True)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extractor_version: Mapped[str] = mapped_column(String(64), default="v6")
    scoring_policy_version: Mapped[str] = mapped_column(String(64), default="WFB-CREDIT-V1")
    analysis_fingerprint: Mapped[str] = mapped_column(String(64), default="")
    score_status: Mapped[str] = mapped_column(String(32), default="NOT_CALCULABLE")
    financial_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    behavioral_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sector_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    partial_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_json: Mapped[str] = mapped_column(Text, default="{}")
    readiness_json: Mapped[str] = mapped_column(Text, default="{}")
    decision_eligibility_json: Mapped[str] = mapped_column(Text, default="{}")
    scoring_view_json: Mapped[str] = mapped_column(Text, default="{}")
    full_audit_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    full_audit_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class DecisionEventModel(Base):
    __tablename__ = "decision_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dossier_id: Mapped[str] = mapped_column(ForeignKey("dossiers.id"), index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32))
    previous_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    score_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_class: Mapped[str | None] = mapped_column(String(16), nullable=True)
    scoring_policy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quality_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    eligibility_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    analysis_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class MemoModel(Base):
    __tablename__ = "memos"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dossier_id: Mapped[str] = mapped_column(ForeignKey("dossiers.id"), index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_json: Mapped[str] = mapped_column(Text, default="{}")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    quality_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    policy_version: Mapped[str] = mapped_column(String(64), default="WFB-CREDIT-V1")
    analysis_fingerprint: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="DRAFT")
    signed_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    signed_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ScoringPolicyModel(Base):
    __tablename__ = "scoring_policies"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), default="")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    validation_status: Mapped[str] = mapped_column(
        String(64),
        default="PENDING_WAFABAIL_BUSINESS_VALIDATION",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class SectorBenchmarkModel(Base):
    __tablename__ = "sector_benchmarks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sector_code: Mapped[str] = mapped_column(String(64), index=True)
    sector_label: Mapped[str] = mapped_column(String(256), default="")
    year: Mapped[int] = mapped_column(Integer)
    version: Mapped[str] = mapped_column(String(64), default="1")
    source: Mapped[str] = mapped_column(String(256), default="")
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_from: Mapped[str | None] = mapped_column(String(32), nullable=True)
    valid_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")


class BamAssessmentModel(Base):
    __tablename__ = "bam_assessments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dossier_id: Mapped[str] = mapped_column(ForeignKey("dossiers.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="MANUAL")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class IncidentAssessmentModel(Base):
    __tablename__ = "incident_assessments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dossier_id: Mapped[str] = mapped_column(ForeignKey("dossiers.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    source: Mapped[str] = mapped_column(String(32), default="MANUAL")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
