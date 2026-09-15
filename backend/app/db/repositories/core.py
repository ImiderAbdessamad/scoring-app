from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisJobModel,
    AnalysisRunModel,
    BamAssessmentModel,
    DecisionEventModel,
    DocumentModel,
    DossierModel,
    IncidentAssessmentModel,
    MemoModel,
    ScoringPolicyModel,
    SectorBenchmarkModel,
)
from app.db.session import session_scope
from app.schemas.create_dossier import StoredDossierRecord, StoredFileMeta


def _now() -> datetime:
    return datetime.utcnow()


class SqlAlchemyDossierRepository:
    def create(self, record: StoredDossierRecord) -> StoredDossierRecord:
        with session_scope() as session:
            self._upsert(session, record)
            session.commit()
        return record

    def get(self, dossier_id: str) -> StoredDossierRecord | None:
        with session_scope() as session:
            row = session.get(DossierModel, dossier_id)
            if row is None:
                return None
            return StoredDossierRecord.model_validate(json.loads(row.payload_json))

    def list(self) -> list[StoredDossierRecord]:
        with session_scope() as session:
            rows = session.scalars(select(DossierModel).order_by(DossierModel.updated_at.desc())).all()
            return [StoredDossierRecord.model_validate(json.loads(r.payload_json)) for r in rows]

    def update(self, record: StoredDossierRecord) -> StoredDossierRecord:
        return self.create(record)

    def update_status(self, dossier_id: str, status: str) -> StoredDossierRecord | None:
        record = self.get(dossier_id)
        if record is None:
            return None
        record = record.model_copy(update={"status": status})
        return self.update(record)

    def update_analysis(self, dossier_id: str, **patch: object) -> StoredDossierRecord | None:
        record = self.get(dossier_id)
        if record is None:
            return None
        mapped: dict = {}
        if "analyse_job_id" in patch:
            mapped["analyseJobId"] = patch["analyse_job_id"]
        if "analyse_status" in patch:
            mapped["analyseStatus"] = patch["analyse_status"]
        if "analyse" in patch:
            mapped["analyse"] = patch["analyse"]
        if "score" in patch:
            mapped["score"] = patch["score"]
        if "status" in patch:
            mapped["status"] = patch["status"]
        if "ice" in patch:
            mapped["ice"] = patch["ice"]
        if "rc" in patch:
            mapped["rc"] = patch["rc"]
        if "name" in patch:
            mapped["name"] = patch["name"]
        if "sector" in patch:
            mapped["sector"] = patch["sector"]
        if "benchmark_sector_code" in patch:
            mapped["benchmarkSectorCode"] = patch["benchmark_sector_code"]
        if "sector_normalized" in patch:
            mapped["sectorNormalized"] = patch["sector_normalized"]
        if "identifiant_fiscal" in patch:
            mapped["identifiantFiscal"] = patch["identifiant_fiscal"]
        if "decisionDate" in patch:
            mapped["decisionDate"] = patch["decisionDate"]
        updated = record.model_copy(update=mapped)
        return self.update(updated)

    def exists(self, dossier_id: str) -> bool:
        return self.get(dossier_id) is not None

    def _upsert(self, session: Session, record: StoredDossierRecord) -> None:
        row = session.get(DossierModel, record.id)
        payload = json.dumps(record.model_dump(), ensure_ascii=False, default=str)
        fields = dict(
            name=record.name,
            ice=record.ice or "",
            identifiant_fiscal=getattr(record, "identifiantFiscal", None),
            rc=record.rc or "",
            sector_raw=getattr(record, "sectorRaw", None) or record.sector,
            sector_normalized=getattr(record, "sectorNormalized", None),
            benchmark_sector_code=getattr(record, "benchmarkSectorCode", None),
            amount=record.amount,
            duration=record.duration,
            nature=record.nature,
            nature_bien=record.natureBien,
            etat=record.etat,
            fournisseur=record.fournisseur,
            apport=record.apport,
            valeur_bien=record.valeurBien,
            valeur_ht=record.valeurHt,
            valeur_ttc=record.valeurTtc,
            proforma_reference=record.proformaReference,
            status=record.status,
            analyse_status=record.analyseStatus,
            payload_json=payload,
            updated_at=_now(),
        )
        if row is None:
            session.add(DossierModel(id=record.id, created_at=_now(), **fields))
        else:
            for key, value in fields.items():
                setattr(row, key, value)
        self._sync_documents(session, record)

    def _sync_documents(self, session: Session, record: StoredDossierRecord) -> None:
        existing = {
            d.object_key: d
            for d in session.scalars(
                select(DocumentModel).where(DocumentModel.dossier_id == record.id)
            )
        }
        seen: set[str] = set()
        for meta in record.files:
            seen.add(meta.objectKey)
            row = existing.get(meta.objectKey)
            sha = getattr(meta, "sha256", None)
            if row is None:
                session.add(
                    DocumentModel(
                        id=uuid.uuid4().hex,
                        dossier_id=record.id,
                        name=meta.name,
                        object_key=meta.objectKey,
                        category=meta.category,
                        mime_type=meta.contentType,
                        size_bytes=meta.size,
                        sha256=sha,
                        version=1,
                        active=True,
                    )
                )
            else:
                row.name = meta.name
                row.size_bytes = meta.size
                row.mime_type = meta.contentType
                row.category = meta.category
                row.sha256 = sha or row.sha256
                row.active = True
        for key, row in existing.items():
            if key not in seen:
                row.active = False


dossier_repository = SqlAlchemyDossierRepository()


class JobRepository:
    def upsert_from_job(self, job) -> None:
        docs = {
            "primary": None if not getattr(job, "primary_document", None) else job.primary_document.__dict__,
            "extra": [d.__dict__ for d in getattr(job, "extra_documents", []) or []],
        }
        api_to_db = {
            "queued": "QUEUED",
            "processing": "RUNNING",
            "completed": "COMPLETED",
            "failed": "FAILED",
            "cancelled": "CANCELLED",
            "interrupted": "INTERRUPTED",
        }
        status = api_to_db.get(job.status, str(job.status).upper())
        with session_scope() as session:
            row = session.get(AnalysisJobModel, job.job_id)
            payload = dict(
                dossier_id=job.dossier_id,
                status=status,
                progress_pct=job.progress_pct,
                current_step=job.current_step,
                current_page=job.current_page,
                pages_total=job.pages_total,
                pages_financial=job.pages_financial,
                pages_skipped=job.pages_skipped,
                pages_failed=job.pages_failed,
                message=job.message or "",
                error=job.error,
                dispatcher=getattr(job, "dispatcher", "local") or "local",
                filename=job.filename,
                documents_json=json.dumps(docs, default=str),
                updated_at=_now(),
            )
            if row is None:
                session.add(AnalysisJobModel(id=job.job_id, **payload))
            else:
                for key, value in payload.items():
                    setattr(row, key, value)
                if status == "RUNNING" and row.started_at is None:
                    row.started_at = _now()
                if status in {"COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED"}:
                    row.completed_at = _now()
            session.commit()

    def get(self, job_id: str) -> AnalysisJobModel | None:
        with session_scope() as session:
            row = session.get(AnalysisJobModel, job_id)
            if row is None:
                return None
            session.expunge(row)
            return row

    def get_for_dossier(self, dossier_id: str) -> AnalysisJobModel | None:
        with session_scope() as session:
            row = session.scalars(
                select(AnalysisJobModel)
                .where(AnalysisJobModel.dossier_id == dossier_id)
                .order_by(AnalysisJobModel.requested_at.desc())
            ).first()
            if row is None:
                return None
            session.expunge(row)
            return row

    def interrupt_running(self) -> int:
        with session_scope() as session:
            rows = session.scalars(
                select(AnalysisJobModel).where(AnalysisJobModel.status == "RUNNING")
            ).all()
            n = 0
            for row in rows:
                row.status = "INTERRUPTED"
                row.message = "Traitement interrompu par redémarrage du service."
                row.completed_at = _now()
                row.updated_at = _now()
                n += 1
            session.commit()
            return n


job_repository = JobRepository()


class AnalysisRunRepository:
    def create(self, **fields) -> AnalysisRunModel:
        run_id = fields.get("id") or uuid.uuid4().hex
        with session_scope() as session:
            row = AnalysisRunModel(id=run_id, **{k: v for k, v in fields.items() if k != "id"})
            session.add(row)
            dossier = session.get(DossierModel, fields["dossier_id"])
            if dossier is not None:
                dossier.current_analysis_run_id = run_id
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def get(self, run_id: str) -> AnalysisRunModel | None:
        with session_scope() as session:
            row = session.get(AnalysisRunModel, run_id)
            if row is None:
                return None
            session.expunge(row)
            return row

    def list_for_dossier(self, dossier_id: str) -> list[AnalysisRunModel]:
        with session_scope() as session:
            rows = session.scalars(
                select(AnalysisRunModel)
                .where(AnalysisRunModel.dossier_id == dossier_id)
                .order_by(AnalysisRunModel.created_at.desc())
            ).all()
            for row in rows:
                session.expunge(row)
            return list(rows)


analysis_run_repository = AnalysisRunRepository()


class DecisionEventRepository:
    def append(self, **fields) -> DecisionEventModel:
        event_id = uuid.uuid4().hex
        with session_scope() as session:
            row = DecisionEventModel(id=event_id, **fields)
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def list_for_dossier(self, dossier_id: str) -> list[DecisionEventModel]:
        with session_scope() as session:
            rows = session.scalars(
                select(DecisionEventModel)
                .where(DecisionEventModel.dossier_id == dossier_id)
                .order_by(DecisionEventModel.created_at.asc())
            ).all()
            for row in rows:
                session.expunge(row)
            return list(rows)


decision_event_repository = DecisionEventRepository()


class MemoRepository:
    def create(self, **fields) -> MemoModel:
        memo_id = uuid.uuid4().hex
        with session_scope() as session:
            version = (
                session.query(MemoModel)
                .filter(MemoModel.dossier_id == fields["dossier_id"])
                .count()
                + 1
            )
            row = MemoModel(id=memo_id, version=version, **fields)
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def get(self, memo_id: str) -> MemoModel | None:
        with session_scope() as session:
            row = session.get(MemoModel, memo_id)
            if row is None:
                return None
            session.expunge(row)
            return row

    def list_for_dossier(self, dossier_id: str) -> list[MemoModel]:
        with session_scope() as session:
            rows = session.scalars(
                select(MemoModel)
                .where(MemoModel.dossier_id == dossier_id)
                .order_by(MemoModel.created_at.desc())
            ).all()
            for row in rows:
                session.expunge(row)
            return list(rows)

    def sign(self, memo_id: str, *, signed_by: str, signed_role: str, content_hash: str) -> MemoModel | None:
        with session_scope() as session:
            row = session.get(MemoModel, memo_id)
            if row is None:
                return None
            row.status = "SIGNED"
            row.signed_by = signed_by
            row.signed_role = signed_role
            row.signed_at = _now()
            row.content_hash = content_hash
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row


memo_repository = MemoRepository()


class SectorBenchmarkRepository:
    def find(self, sector_code: str | None, year: int | None) -> SectorBenchmarkModel | None:
        if not sector_code:
            return None
        with session_scope() as session:
            stmt = select(SectorBenchmarkModel).where(SectorBenchmarkModel.sector_code == sector_code)
            if year is not None:
                stmt = stmt.where(SectorBenchmarkModel.year == year)
            row = session.scalars(stmt.order_by(SectorBenchmarkModel.year.desc())).first()
            if row is None:
                return None
            session.expunge(row)
            return row


sector_benchmark_repository = SectorBenchmarkRepository()


class RiskRepository:
    def get_bam(self, dossier_id: str) -> BamAssessmentModel | None:
        with session_scope() as session:
            row = session.scalars(
                select(BamAssessmentModel)
                .where(BamAssessmentModel.dossier_id == dossier_id)
                .order_by(BamAssessmentModel.updated_at.desc())
            ).first()
            if row is None:
                return None
            session.expunge(row)
            return row

    def upsert_bam(self, dossier_id: str, **fields) -> BamAssessmentModel:
        with session_scope() as session:
            row = session.scalars(
                select(BamAssessmentModel).where(BamAssessmentModel.dossier_id == dossier_id)
            ).first()
            if row is None:
                row = BamAssessmentModel(id=uuid.uuid4().hex, dossier_id=dossier_id, **fields)
                session.add(row)
            else:
                for key, value in fields.items():
                    setattr(row, key, value)
                row.updated_at = _now()
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def get_incidents(self, dossier_id: str) -> IncidentAssessmentModel | None:
        with session_scope() as session:
            row = session.scalars(
                select(IncidentAssessmentModel)
                .where(IncidentAssessmentModel.dossier_id == dossier_id)
                .order_by(IncidentAssessmentModel.updated_at.desc())
            ).first()
            if row is None:
                return None
            session.expunge(row)
            return row

    def upsert_incidents(self, dossier_id: str, **fields) -> IncidentAssessmentModel:
        with session_scope() as session:
            row = session.scalars(
                select(IncidentAssessmentModel).where(
                    IncidentAssessmentModel.dossier_id == dossier_id
                )
            ).first()
            if row is None:
                row = IncidentAssessmentModel(id=uuid.uuid4().hex, dossier_id=dossier_id, **fields)
                session.add(row)
            else:
                for key, value in fields.items():
                    setattr(row, key, value)
                row.updated_at = _now()
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row


risk_repository = RiskRepository()


class ScoringPolicyRepository:
    def get(self, version: str) -> ScoringPolicyModel | None:
        with session_scope() as session:
            row = session.get(ScoringPolicyModel, version)
            if row is None:
                return None
            session.expunge(row)
            return row

    def ensure_default(self, version: str, name: str, config: dict) -> None:
        with session_scope() as session:
            if session.get(ScoringPolicyModel, version) is not None:
                return
            session.add(
                ScoringPolicyModel(
                    version=version,
                    name=name,
                    config_json=json.dumps(config, ensure_ascii=False),
                    active=True,
                    validation_status="PENDING_WAFABAIL_BUSINESS_VALIDATION",
                )
            )
            session.commit()


scoring_policy_repository = ScoringPolicyRepository()
