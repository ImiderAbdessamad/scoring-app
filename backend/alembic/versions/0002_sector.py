"""0002 sector HCP datasets observations sync snapshots

Revision ID: 0002_sector
Revises: 0001_wfb
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_sector"
down_revision = "0001_wfb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sector_data_sources",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("code", sa.String(32), unique=True),
        sa.Column("name", sa.String(256), server_default="HCP"),
        sa.Column("provider_type", sa.String(64), server_default="hcp_ckan"),
        sa.Column("active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "sector_datasets",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sector_data_sources.id")),
        sa.Column("external_dataset_id", sa.String(64)),
        sa.Column("name", sa.String(512), server_default=""),
        sa.Column("metric", sa.String(64), server_default="VALUE_ADDED"),
        sa.Column("frequency", sa.String(32), server_default="ANNUAL"),
        sa.Column("price_type", sa.String(32), server_default="CURRENT"),
        sa.Column("base_year", sa.Integer()),
        sa.Column("unit", sa.String(32), server_default="M MAD"),
        sa.Column("resource_id", sa.String(128)),
        sa.Column("resource_name", sa.String(256)),
        sa.Column("object_key", sa.String(1024)),
        sa.Column("source_created_at", sa.String(64)),
        sa.Column("source_updated_at", sa.String(64)),
        sa.Column("last_checked_at", sa.DateTime()),
        sa.Column("last_downloaded_at", sa.DateTime()),
        sa.Column("last_successful_sync_at", sa.DateTime()),
        sa.Column("resource_sha256", sa.String(64)),
        sa.Column("resource_size", sa.Integer()),
        sa.Column("active", sa.Boolean(), server_default=sa.true()),
        sa.UniqueConstraint("source_id", "external_dataset_id", name="uq_sector_dataset"),
    )
    op.create_table(
        "sector_observations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("dataset_id", sa.String(64), sa.ForeignKey("sector_datasets.id")),
        sa.Column("sector_code", sa.String(128)),
        sa.Column("sector_label", sa.String(512), server_default=""),
        sa.Column("period_type", sa.String(32), server_default="ANNUAL"),
        sa.Column("year", sa.Integer()),
        sa.Column("quarter", sa.Integer(), server_default="0"),
        sa.Column("value", sa.Numeric(20, 4)),
        sa.Column("unit", sa.String(32), server_default="M MAD"),
        sa.Column("metric", sa.String(64), server_default="VALUE_ADDED"),
        sa.Column("price_type", sa.String(32), server_default="CURRENT"),
        sa.Column("base_year", sa.Integer()),
        sa.Column("source_dataset_version", sa.String(128)),
        sa.Column("resource_sha256", sa.String(64)),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("dataset_id", "sector_code", "year", "quarter", name="uq_sector_observation"),
    )
    op.create_table(
        "sector_sync_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("dataset_id", sa.String(64)),
        sa.Column("external_dataset_id", sa.String(64)),
        sa.Column("status", sa.String(32), server_default="STARTED"),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("remote_updated_at", sa.String(64)),
        sa.Column("previous_hash", sa.String(64)),
        sa.Column("new_hash", sa.String(64)),
        sa.Column("rows_read", sa.Integer(), server_default="0"),
        sa.Column("rows_inserted", sa.Integer(), server_default="0"),
        sa.Column("rows_updated", sa.Integer(), server_default="0"),
        sa.Column("error", sa.Text()),
    )
    op.create_table(
        "sector_mappings",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("raw_activity_normalized", sa.String(512)),
        sa.Column("hcp_sector_code", sa.String(128)),
        sa.Column("hcp_sector_label", sa.String(512)),
        sa.Column("mapping_method", sa.String(32), server_default="KEYWORD"),
        sa.Column("confidence", sa.Numeric(6, 4)),
        sa.Column("validated", sa.Boolean(), server_default=sa.false()),
        sa.Column("validated_by", sa.String(256)),
        sa.Column("validated_at", sa.DateTime()),
    )
    op.create_table(
        "sector_analysis_snapshots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("dossier_id", sa.String(64)),
        sa.Column("analysis_run_id", sa.String(64)),
        sa.Column("sector_code", sa.String(128)),
        sa.Column("sector_label", sa.String(512)),
        sa.Column("data_version_json", sa.Text(), server_default="{}"),
        sa.Column("result_json", sa.Text(), server_default="{}"),
        sa.Column("created_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("sector_analysis_snapshots")
    op.drop_table("sector_mappings")
    op.drop_table("sector_sync_runs")
    op.drop_table("sector_observations")
    op.drop_table("sector_datasets")
    op.drop_table("sector_data_sources")
