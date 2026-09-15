"""0001 dossiers documents jobs runs decisions memos policies benchmarks risk

Revision ID: 0001_wfb
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_wfb"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dossiers",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(512), nullable=False, server_default=""),
        sa.Column("ice", sa.String(32), server_default=""),
        sa.Column("identifiant_fiscal", sa.String(32)),
        sa.Column("rc", sa.String(64), server_default=""),
        sa.Column("sector_raw", sa.String(256)),
        sa.Column("sector_normalized", sa.String(128)),
        sa.Column("benchmark_sector_code", sa.String(64)),
        sa.Column("amount", sa.Float(), server_default="0"),
        sa.Column("duration", sa.Integer(), server_default="0"),
        sa.Column("nature", sa.String(32), server_default=""),
        sa.Column("nature_bien", sa.String(256), server_default=""),
        sa.Column("etat", sa.String(32), server_default=""),
        sa.Column("fournisseur", sa.String(256), server_default=""),
        sa.Column("apport", sa.Float(), server_default="0"),
        sa.Column("valeur_bien", sa.Float(), server_default="0"),
        sa.Column("valeur_ht", sa.Float(), server_default="0"),
        sa.Column("valeur_ttc", sa.Float(), server_default="0"),
        sa.Column("proforma_reference", sa.String(128), server_default=""),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("analyse_status", sa.String(32)),
        sa.Column("current_analysis_run_id", sa.String(64)),
        sa.Column("current_decision", sa.String(32)),
        sa.Column("payload_json", sa.Text(), server_default="{}"),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("dossier_id", sa.String(64), sa.ForeignKey("dossiers.id")),
        sa.Column("name", sa.String(512)),
        sa.Column("object_key", sa.String(1024)),
        sa.Column("category", sa.String(64)),
        sa.Column("mime_type", sa.String(128)),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("sha256", sa.String(64)),
        sa.Column("version", sa.Integer()),
        sa.Column("active", sa.Boolean()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "document_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("document_id", sa.String(64), sa.ForeignKey("documents.id")),
        sa.Column("object_key", sa.String(1024)),
        sa.Column("sha256", sa.String(64)),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("version", sa.Integer()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("dossier_id", sa.String(64), sa.ForeignKey("dossiers.id")),
        sa.Column("status", sa.String(32)),
        sa.Column("progress_pct", sa.Integer()),
        sa.Column("current_step", sa.String(64)),
        sa.Column("current_page", sa.Integer()),
        sa.Column("pages_total", sa.Integer()),
        sa.Column("pages_financial", sa.Integer()),
        sa.Column("pages_skipped", sa.Integer()),
        sa.Column("pages_failed", sa.Integer()),
        sa.Column("message", sa.Text()),
        sa.Column("error", sa.Text()),
        sa.Column("dispatcher", sa.String(32)),
        sa.Column("filename", sa.String(512)),
        sa.Column("documents_json", sa.Text()),
        sa.Column("analysis_run_id", sa.String(64)),
        sa.Column("requested_at", sa.DateTime()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("dossier_id", sa.String(64), sa.ForeignKey("dossiers.id")),
        sa.Column("job_id", sa.String(64)),
        sa.Column("extractor_version", sa.String(64)),
        sa.Column("scoring_policy_version", sa.String(64)),
        sa.Column("analysis_fingerprint", sa.String(64)),
        sa.Column("score_status", sa.String(32)),
        sa.Column("financial_score", sa.Float()),
        sa.Column("behavioral_score", sa.Float()),
        sa.Column("sector_score", sa.Float()),
        sa.Column("partial_score", sa.Float()),
        sa.Column("final_score", sa.Float()),
        sa.Column("quality_json", sa.Text()),
        sa.Column("readiness_json", sa.Text()),
        sa.Column("decision_eligibility_json", sa.Text()),
        sa.Column("scoring_view_json", sa.Text()),
        sa.Column("full_audit_object_key", sa.String(1024)),
        sa.Column("full_audit_sha256", sa.String(64)),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "decision_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("dossier_id", sa.String(64), sa.ForeignKey("dossiers.id")),
        sa.Column("analysis_run_id", sa.String(64)),
        sa.Column("event_type", sa.String(32)),
        sa.Column("previous_status", sa.String(32)),
        sa.Column("new_status", sa.String(32)),
        sa.Column("actor_id", sa.String(64)),
        sa.Column("actor_name", sa.String(256)),
        sa.Column("actor_role", sa.String(64)),
        sa.Column("reason", sa.Text()),
        sa.Column("comment", sa.Text()),
        sa.Column("score_status", sa.String(32)),
        sa.Column("score_value", sa.Float()),
        sa.Column("score_class", sa.String(16)),
        sa.Column("scoring_policy_version", sa.String(64)),
        sa.Column("quality_snapshot_json", sa.Text()),
        sa.Column("eligibility_snapshot_json", sa.Text()),
        sa.Column("analysis_fingerprint", sa.String(64)),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "memos",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("dossier_id", sa.String(64), sa.ForeignKey("dossiers.id")),
        sa.Column("analysis_run_id", sa.String(64)),
        sa.Column("version", sa.Integer()),
        sa.Column("content_json", sa.Text()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("score_snapshot_json", sa.Text()),
        sa.Column("quality_snapshot_json", sa.Text()),
        sa.Column("policy_version", sa.String(64)),
        sa.Column("analysis_fingerprint", sa.String(64)),
        sa.Column("status", sa.String(16)),
        sa.Column("signed_by", sa.String(256)),
        sa.Column("signed_role", sa.String(64)),
        sa.Column("signed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "scoring_policies",
        sa.Column("version", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(256)),
        sa.Column("config_json", sa.Text()),
        sa.Column("active", sa.Boolean()),
        sa.Column("validation_status", sa.String(64)),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "sector_benchmarks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("sector_code", sa.String(64)),
        sa.Column("sector_label", sa.String(256)),
        sa.Column("year", sa.Integer()),
        sa.Column("version", sa.String(64)),
        sa.Column("source", sa.String(256)),
        sa.Column("sample_size", sa.Integer()),
        sa.Column("valid_from", sa.String(32)),
        sa.Column("valid_to", sa.String(32)),
        sa.Column("metrics_json", sa.Text()),
    )
    op.create_table(
        "bam_assessments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("dossier_id", sa.String(64), sa.ForeignKey("dossiers.id")),
        sa.Column("status", sa.String(32)),
        sa.Column("rating", sa.Integer()),
        sa.Column("source", sa.String(32)),
        sa.Column("comment", sa.Text()),
        sa.Column("checked_by", sa.String(256)),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_table(
        "incident_assessments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("dossier_id", sa.String(64), sa.ForeignKey("dossiers.id")),
        sa.Column("status", sa.String(32)),
        sa.Column("source", sa.String(32)),
        sa.Column("comment", sa.Text()),
        sa.Column("checked_by", sa.String(256)),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )


def downgrade() -> None:
    for table in [
        "incident_assessments",
        "bam_assessments",
        "sector_benchmarks",
        "scoring_policies",
        "memos",
        "decision_events",
        "analysis_runs",
        "analysis_jobs",
        "document_versions",
        "documents",
        "dossiers",
    ]:
        op.drop_table(table)
