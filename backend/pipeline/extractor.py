"""Feature extraction helpers for pipeline processing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Feature, Snapshot
from backend.pipeline.bus_factor import calculate_bus_factor


def _current_week_start_utc() -> datetime.date:
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=today.weekday())


def extract_bus_factor_for_project(session: Session, project_id: int) -> int:
    """Extract and persist bus factor for the latest snapshot of a project."""
    latest_snapshot = session.execute(
        select(Snapshot)
        .where(Snapshot.project_id == project_id)
        .order_by(Snapshot.scraped_at.desc(), Snapshot.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    contributors = []
    if latest_snapshot and isinstance(latest_snapshot.raw_json, dict):
        raw_contributors = latest_snapshot.raw_json.get("contributor_stats", [])
        if isinstance(raw_contributors, list):
            contributors = raw_contributors

    bus_factor = calculate_bus_factor(contributors)
    week_start = _current_week_start_utc()

    existing_feature = session.execute(
        select(Feature).where(Feature.project_id == project_id, Feature.week_start == week_start).limit(1)
    ).scalar_one_or_none()

    if existing_feature:
        existing_feature.bus_factor = bus_factor
    else:
        session.add(
            Feature(
                project_id=project_id,
                week_start=week_start,
                contributor_delta_pct=0.0,
                commit_velocity_delta=0.0,
                issue_close_rate=0.0,
                bus_factor=bus_factor,
                maintainer_inactivity_days=0,
                news_sentiment_avg=0.0,
                days_since_last_release=0,
            )
        )

    session.flush()
    return bus_factor
