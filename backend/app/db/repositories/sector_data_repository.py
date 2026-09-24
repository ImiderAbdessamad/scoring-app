from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select

from app.db.models.sector_data import (
    SectorAnalysisSnapshotModel,
    SectorDataSourceModel,
    SectorDatasetModel,
    SectorObservationModel,
    SectorSyncRunModel,
)
from app.db.session import session_scope
from app.sector.domain import ParsedObservation


def _now() -> datetime:
    return datetime.utcnow()


class SectorDataRepository:
    def ensure_hcp_source(self) -> SectorDataSourceModel:
        with session_scope() as session:
            row = session.scalars(
                select(SectorDataSourceModel).where(SectorDataSourceModel.code == "HCP")
            ).first()
            if row is None:
                row = SectorDataSourceModel(
                    id=uuid.uuid4().hex,
                    code="HCP",
                    name="Haut Commissariat au Plan",
                    provider_type="hcp_ckan",
                    active=True,
                )
                session.add(row)
                session.commit()
                session.refresh(row)
            session.expunge(row)
            return row

    def get_or_create_dataset(
        self,
        *,
        source_id: str,
        external_dataset_id: str,
        name: str,
        metric: str,
        frequency: str,
        price_type: str,
        base_year: int | None,
        unit: str,
    ) -> SectorDatasetModel:
        with session_scope() as session:
            row = session.scalars(
                select(SectorDatasetModel).where(
                    SectorDatasetModel.source_id == source_id,
                    SectorDatasetModel.external_dataset_id == external_dataset_id,
                )
            ).first()
            if row is None:
                row = SectorDatasetModel(
                    id=uuid.uuid4().hex,
                    source_id=source_id,
                    external_dataset_id=external_dataset_id,
                    name=name,
                    metric=metric,
                    frequency=frequency,
                    price_type=price_type,
                    base_year=base_year,
                    unit=unit,
                    active=True,
                )
                session.add(row)
                session.commit()
                session.refresh(row)
            session.expunge(row)
            return row

    def list_datasets(self) -> list[SectorDatasetModel]:
        with session_scope() as session:
            rows = list(session.scalars(select(SectorDatasetModel)).all())
            for row in rows:
                session.expunge(row)
            return rows

    def get_dataset_by_external(
        self,
        external_dataset_id: str,
        *,
        source_id: str | None = None,
    ) -> SectorDatasetModel | None:
        with session_scope() as session:
            stmt = select(SectorDatasetModel).where(
                SectorDatasetModel.external_dataset_id == external_dataset_id
            )
            if source_id:
                stmt = stmt.where(SectorDatasetModel.source_id == source_id)
            row = session.scalars(stmt).first()
            if row is None:
                return None
            session.expunge(row)
            return row

    def touch_checked(self, dataset_pk: str, **fields) -> None:
        with session_scope() as session:
            row = session.get(SectorDatasetModel, dataset_pk)
            if row is None:
                return
            for key, value in fields.items():
                setattr(row, key, value)
            row.last_checked_at = _now()
            session.commit()

    def observation_count(self, dataset_pk: str) -> int:
        with session_scope() as session:
            return int(
                session.scalar(
                    select(func.count()).select_from(SectorObservationModel).where(
                        SectorObservationModel.dataset_id == dataset_pk
                    )
                )
                or 0
            )

    def list_observations(
        self,
        *,
        dataset_pk: str,
        sector_code: str,
        period_type: str | None = None,
    ) -> list[SectorObservationModel]:
        with session_scope() as session:
            stmt = select(SectorObservationModel).where(
                SectorObservationModel.dataset_id == dataset_pk,
                SectorObservationModel.sector_code == sector_code,
            )
            if period_type:
                stmt = stmt.where(SectorObservationModel.period_type == period_type)
            stmt = stmt.order_by(SectorObservationModel.year, SectorObservationModel.quarter)
            rows = list(session.scalars(stmt).all())
            for row in rows:
                session.expunge(row)
            return rows

    def replace_observations(
        self,
        *,
        dataset_pk: str,
        observations: list[ParsedObservation],
        resource_sha256: str,
        source_version: str | None,
    ) -> tuple[int, int]:
        inserted = 0
        updated = 0
        with session_scope() as session:
            for item in observations:
                quarter = item.quarter or 0
                existing = session.scalars(
                    select(SectorObservationModel).where(
                        SectorObservationModel.dataset_id == dataset_pk,
                        SectorObservationModel.sector_code == item.sector_code,
                        SectorObservationModel.year == item.year,
                        SectorObservationModel.quarter == quarter,
                    )
                ).first()
                if existing is None:
                    session.add(
                        SectorObservationModel(
                            id=uuid.uuid4().hex,
                            dataset_id=dataset_pk,
                            sector_code=item.sector_code,
                            sector_label=item.sector_label,
                            period_type=item.period_type,
                            year=item.year,
                            quarter=quarter,
                            value=item.value,
                            unit=item.unit,
                            metric=item.metric,
                            price_type=item.price_type,
                            base_year=item.base_year,
                            source_dataset_version=source_version,
                            resource_sha256=resource_sha256,
                        )
                    )
                    inserted += 1
                else:
                    existing.value = item.value
                    existing.unit = item.unit
                    existing.sector_label = item.sector_label
                    existing.resource_sha256 = resource_sha256
                    existing.source_dataset_version = source_version
                    updated += 1
            session.commit()
        return inserted, updated

    def add_sync_run(self, **fields) -> SectorSyncRunModel:
        with session_scope() as session:
            row = SectorSyncRunModel(id=uuid.uuid4().hex, **fields)
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def finish_sync_run(self, run_id: str, **fields) -> None:
        with session_scope() as session:
            row = session.get(SectorSyncRunModel, run_id)
            if row is None:
                return
            for key, value in fields.items():
                setattr(row, key, value)
            row.finished_at = _now()
            session.commit()

    def latest_sync(self, external_dataset_id: str) -> SectorSyncRunModel | None:
        with session_scope() as session:
            row = session.scalars(
                select(SectorSyncRunModel)
                .where(SectorSyncRunModel.external_dataset_id == external_dataset_id)
                .order_by(SectorSyncRunModel.started_at.desc())
            ).first()
            if row is None:
                return None
            session.expunge(row)
            return row

    def save_snapshot(
        self,
        *,
        dossier_id: str,
        analysis_run_id: str | None,
        sector_code: str | None,
        sector_label: str | None,
        data_version: dict,
        result: dict,
    ) -> SectorAnalysisSnapshotModel:
        with session_scope() as session:
            row = SectorAnalysisSnapshotModel(
                id=uuid.uuid4().hex,
                dossier_id=dossier_id,
                analysis_run_id=analysis_run_id,
                sector_code=sector_code,
                sector_label=sector_label,
                data_version_json=json.dumps(data_version, default=str),
                result_json=json.dumps(result, default=str),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def get_snapshot_for_run(self, analysis_run_id: str) -> SectorAnalysisSnapshotModel | None:
        with session_scope() as session:
            row = session.scalars(
                select(SectorAnalysisSnapshotModel)
                .where(SectorAnalysisSnapshotModel.analysis_run_id == analysis_run_id)
                .order_by(SectorAnalysisSnapshotModel.created_at.desc())
            ).first()
            if row is None:
                return None
            session.expunge(row)
            return row

    def get_latest_snapshot(self, dossier_id: str) -> SectorAnalysisSnapshotModel | None:
        with session_scope() as session:
            row = session.scalars(
                select(SectorAnalysisSnapshotModel)
                .where(SectorAnalysisSnapshotModel.dossier_id == dossier_id)
                .order_by(SectorAnalysisSnapshotModel.created_at.desc())
            ).first()
            if row is None:
                return None
            session.expunge(row)
            return row


sector_data_repository = SectorDataRepository()
