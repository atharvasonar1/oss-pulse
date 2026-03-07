"""create core tables

Revision ID: 20260306_0001
Revises:
Create Date: 2026-03-06 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260306_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("repo", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("html_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("owner", "repo", name="uq_projects_owner_repo"),
    )

    op.create_table(
        "snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_snapshots_project_id", "snapshots", ["project_id"], unique=False)

    op.create_table(
        "features",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("contributor_delta_pct", sa.Float(), nullable=False),
        sa.Column("commit_velocity_delta", sa.Float(), nullable=False),
        sa.Column("issue_close_rate", sa.Float(), nullable=False),
        sa.Column("bus_factor", sa.Integer(), nullable=False),
        sa.Column("maintainer_inactivity_days", sa.Integer(), nullable=False),
        sa.Column("news_sentiment_avg", sa.Float(), nullable=False),
        sa.Column("days_since_last_release", sa.Integer(), nullable=False),
        sa.UniqueConstraint("project_id", "week_start", name="uq_features_project_week"),
    )
    op.create_index("ix_features_project_id", "features", ["project_id"], unique=False)
    op.create_index("ix_features_week_start", "features", ["week_start"], unique=False)

    op.create_table(
        "risk_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("top_feature_1", sa.Text(), nullable=True),
        sa.Column("top_feature_2", sa.Text(), nullable=True),
        sa.Column("top_feature_3", sa.Text(), nullable=True),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_risk_scores_score_range"),
    )
    op.create_index("ix_risk_scores_project_id", "risk_scores", ["project_id"], unique=False)
    op.create_index("ix_risk_scores_scored_at", "risk_scores", ["scored_at"], unique=False)

    op.create_table(
        "news_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=False),
    )
    op.create_index("ix_news_items_project_id", "news_items", ["project_id"], unique=False)
    op.create_index("ix_news_items_published_at", "news_items", ["published_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_news_items_published_at", table_name="news_items")
    op.drop_index("ix_news_items_project_id", table_name="news_items")
    op.drop_table("news_items")

    op.drop_index("ix_risk_scores_scored_at", table_name="risk_scores")
    op.drop_index("ix_risk_scores_project_id", table_name="risk_scores")
    op.drop_table("risk_scores")

    op.drop_index("ix_features_week_start", table_name="features")
    op.drop_index("ix_features_project_id", table_name="features")
    op.drop_table("features")

    op.drop_index("ix_snapshots_project_id", table_name="snapshots")
    op.drop_table("snapshots")

    op.drop_table("projects")
