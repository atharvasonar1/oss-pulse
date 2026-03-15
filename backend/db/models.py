"""SQLAlchemy ORM models for OSS Pulse core persistence tables."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Base class for all ORM models."""


json_type = JSON().with_variant(JSONB, "postgresql")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("owner", "repo", name="uq_projects_owner_repo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    repo: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_url: Mapped[str] = mapped_column(Text, nullable=False)
    dependent_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    snapshots: Mapped[list[Snapshot]] = relationship(back_populates="project", cascade="all, delete-orphan")
    features: Mapped[list[Feature]] = relationship(back_populates="project", cascade="all, delete-orphan")
    risk_scores: Mapped[list[RiskScore]] = relationship(back_populates="project", cascade="all, delete-orphan")
    news_items: Mapped[list[NewsItem]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    raw_json: Mapped[dict] = mapped_column(json_type, nullable=False)

    project: Mapped[Project] = relationship(back_populates="snapshots")


class Feature(Base):
    __tablename__ = "features"
    __table_args__ = (UniqueConstraint("project_id", "week_start", name="uq_features_project_week"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    contributor_delta_pct: Mapped[float] = mapped_column(Float, nullable=False)
    commit_velocity_delta: Mapped[float] = mapped_column(Float, nullable=False)
    issue_close_rate: Mapped[float] = mapped_column(Float, nullable=False)
    bus_factor: Mapped[int] = mapped_column(Integer, nullable=False)
    maintainer_inactivity_days: Mapped[int] = mapped_column(Integer, nullable=False)
    news_sentiment_avg: Mapped[float] = mapped_column(Float, nullable=False)
    days_since_last_release: Mapped[int] = mapped_column(Integer, nullable=False)

    project: Mapped[Project] = relationship(back_populates="features")


class RiskScore(Base):
    __tablename__ = "risk_scores"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_risk_scores_score_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    top_feature_1: Mapped[str | None] = mapped_column(Text, nullable=True)
    top_feature_2: Mapped[str | None] = mapped_column(Text, nullable=True)
    top_feature_3: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="risk_scores")


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)

    project: Mapped[Project] = relationship(back_populates="news_items")
