"""initial ASTERIA backend schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    metadata = sa.MetaData()

    op.create_table(
        "raw_data",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column("mission", sa.String(32), nullable=False),
        sa.Column("sector", sa.Integer(), nullable=True),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_raw_data_target_id", "raw_data", ["target_id"])
    op.create_index("ix_raw_data_mission", "raw_data", ["mission"])

    op.create_table(
        "processed_light_curves",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("light_curve_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("raw_data_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cache_path", sa.Text(), nullable=True),
        sa.Column("preprocessing_version", sa.String(64), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["raw_data_id"], ["raw_data.id"]),
    )

    op.create_table(
        "model_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("artifact_uri", sa.Text(), nullable=False),
        sa.Column("feature_schema_version", sa.String(64), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "candidate_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("light_curve_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column("period_days", sa.Float(), nullable=False),
        sa.Column("depth", sa.Float(), nullable=False),
        sa.Column("duration_hours", sa.Float(), nullable=False),
        sa.Column("bls_power", sa.Float(), nullable=False),
        sa.Column("snr", sa.Float(), nullable=True),
        sa.Column("planet_probability", sa.Float(), nullable=True),
        sa.Column("prediction", sa.String(64), nullable=True),
        sa.Column("model_name", sa.String(128), nullable=True),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_candidate_results_light_curve_id", "candidate_results", ["light_curve_id"])
    op.create_index("ix_candidate_results_target_id", "candidate_results", ["target_id"])

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_path", sa.Text(), nullable=False),
        sa.Column("report_type", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_reports_candidate_id", "reports", ["candidate_id"])

    op.create_table(
        "pipeline_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("event", sa.String(128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("pipeline_logs")
    op.drop_index("ix_reports_candidate_id", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_candidate_results_target_id", table_name="candidate_results")
    op.drop_index("ix_candidate_results_light_curve_id", table_name="candidate_results")
    op.drop_table("candidate_results")
    op.drop_table("model_registry")
    op.drop_table("processed_light_curves")
    op.drop_index("ix_raw_data_mission", table_name="raw_data")
    op.drop_index("ix_raw_data_target_id", table_name="raw_data")
    op.drop_table("raw_data")
