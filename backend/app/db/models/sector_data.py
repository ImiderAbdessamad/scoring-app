from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.utcnow()


class SectorDataSourceModel(Base):
    __tablename__ = "sector_data_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(256), default="HCP")
    provider_type: Mapped[str] = mapped_column(String(64), default="hcp_ckan")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class SectorDatasetModel(Base):
    __tablename__ = "sector_datasets"
    __table_args__ = (UniqueConstraint("source_id", "external_dataset_id", name="uq_sector_dataset"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sector_data_sources.id"), index=True)
    external_dataset_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(512), default="")
    metric: Mapped[str] = mapped_column(String(64), default="VALUE_ADDED")
    frequency: Mapped[str] = mapped_column(String(32), default="ANNUAL")
    price_type: Mapped[str] = mapped_column(String(32), default="CURRENT")
    base_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit: Mapped[str] = mapped_column(String(32), default="M MAD")
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resource_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_downloaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resource_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SectorObservationModel(Base):
    __tablename__ = "sector_observations"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id",
            "sector_code",
            "year",
            "quarter",
            name="uq_sector_observation",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("sector_datasets.id"), index=True)
    sector_code: Mapped[str] = mapped_column(String(128), index=True)
    sector_label: Mapped[str] = mapped_column(String(512), default="")
    period_type: Mapped[str] = mapped_column(String(32), default="ANNUAL")
    year: Mapped[int] = mapped_column(Integer)
    quarter: Mapped[int] = mapped_column(Integer, default=0)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    unit: Mapped[str] = mapped_column(String(32), default="M MAD")
    metric: Mapped[str] = mapped_column(String(64), default="VALUE_ADDED")
    price_type: Mapped[str] = mapped_column(String(32), default="CURRENT")
    base_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_dataset_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resource_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class SectorSyncRunModel(Base):
    __tablename__ = "sector_sync_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str | None] = mapped_column(String(64), index=True)
    external_dataset_id: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="STARTED")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remote_updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0)
    rows_updated: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class SectorMappingModel(Base):
    __tablename__ = "sector_mappings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    raw_activity_normalized: Mapped[str] = mapped_column(String(512), index=True)
    hcp_sector_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    hcp_sector_label: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mapping_method: Mapped[str] = mapped_column(String(32), default="KEYWORD")
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    validated_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SectorAnalysisSnapshotModel(Base):
    __tablename__ = "sector_analysis_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dossier_id: Mapped[str] = mapped_column(String(64), index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    sector_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sector_label: Mapped[str | None] = mapped_column(String(512), nullable=True)
    data_version_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
