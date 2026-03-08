"""Data loading utilities for ML training."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Feature, Project


FEATURE_COLUMNS = [
    "contributor_delta_pct",
    "commit_velocity_delta",
    "issue_close_rate",
    "bus_factor",
    "maintainer_inactivity_days",
    "news_sentiment_avg",
    "days_since_last_release",
]

REQUIRED_LABEL_COLUMNS = [
    "owner",
    "repo",
    "disruption_start_date",
    "disruption_end_date",
    "disruption_type",
    "label",
    "notes",
]


def load_from_csv(csv_path: str) -> pd.DataFrame:
    """Load and validate labeled event windows from CSV."""
    df = pd.read_csv(csv_path)
    missing = [column for column in REQUIRED_LABEL_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in {csv_path}: {missing}")

    cleaned = df[REQUIRED_LABEL_COLUMNS].copy()
    cleaned["owner"] = cleaned["owner"].astype(str).str.strip()
    cleaned["repo"] = cleaned["repo"].astype(str).str.strip()
    cleaned["disruption_start_date"] = pd.to_datetime(cleaned["disruption_start_date"], errors="raise").dt.date
    cleaned["disruption_end_date"] = pd.to_datetime(cleaned["disruption_end_date"], errors="raise").dt.date
    cleaned["label"] = pd.to_numeric(cleaned["label"], errors="raise").astype(int)

    invalid_labels = cleaned[~cleaned["label"].isin([0, 1])]
    if not invalid_labels.empty:
        raise ValueError("Label column must contain only 0 or 1.")

    return cleaned


def load_feature_vectors(session: Session) -> tuple[np.ndarray, np.ndarray]:
    """Join features to labeled windows and return X, y arrays."""
    labels_df = load_from_csv(str(Path("docs") / "labeled_events.csv"))

    query = (
        select(
            Project.owner,
            Project.repo,
            Feature.week_start,
            Feature.contributor_delta_pct,
            Feature.commit_velocity_delta,
            Feature.issue_close_rate,
            Feature.bus_factor,
            Feature.maintainer_inactivity_days,
            Feature.news_sentiment_avg,
            Feature.days_since_last_release,
        )
        .join(Project, Feature.project_id == Project.id)
        .order_by(Project.owner.asc(), Project.repo.asc(), Feature.week_start.asc())
    )
    rows = session.execute(query).all()

    if not rows:
        return np.empty((0, len(FEATURE_COLUMNS)), dtype=float), np.empty((0,), dtype=int)

    feature_rows = pd.DataFrame(
        [
            {
                "owner": row.owner,
                "repo": row.repo,
                "week_start": row.week_start,
                "contributor_delta_pct": row.contributor_delta_pct,
                "commit_velocity_delta": row.commit_velocity_delta,
                "issue_close_rate": row.issue_close_rate,
                "bus_factor": row.bus_factor,
                "maintainer_inactivity_days": row.maintainer_inactivity_days,
                "news_sentiment_avg": row.news_sentiment_avg,
                "days_since_last_release": row.days_since_last_release,
            }
            for row in rows
        ]
    )

    merged = feature_rows.merge(labels_df, on=["owner", "repo"], how="inner")
    matched = merged[
        (merged["week_start"] >= merged["disruption_start_date"])
        & (merged["week_start"] <= merged["disruption_end_date"])
    ].copy()

    if matched.empty:
        return np.empty((0, len(FEATURE_COLUMNS)), dtype=float), np.empty((0,), dtype=int)

    X = matched[FEATURE_COLUMNS].to_numpy(dtype=float)
    y = matched["label"].to_numpy(dtype=int)
    return X, y
