"""Snapshot storage utilities for scraper output."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.db.models import Snapshot


def store_snapshot(session: Session, project_id: int, raw_data: dict[str, Any]) -> Snapshot:
    """Persist one scrape payload into the snapshots table."""
    snapshot = Snapshot(
        project_id=project_id,
        scraped_at=datetime.now(timezone.utc),
        raw_json=raw_data,
    )
    session.add(snapshot)
    session.flush()
    session.refresh(snapshot)
    return snapshot
