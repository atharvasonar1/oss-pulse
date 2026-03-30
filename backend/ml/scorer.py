"""Bridge layer for project scoring between ML inference and database persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Feature, RiskScore
from backend.ml.data import FEATURE_COLUMNS
from backend.ml.inference import fallback_heuristic, load_model, predict_with_explanation


MODEL_PATH = "backend/ml/models/xgb_v1.pkl"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _zero_feature_dict() -> dict[str, float]:
    return {name: 0.0 for name in FEATURE_COLUMNS}


def _feature_row_to_dict(feature_row: Feature | None) -> dict[str, float]:
    if feature_row is None:
        return _zero_feature_dict()

    return {
        "contributor_delta_pct": float(feature_row.contributor_delta_pct),
        "commit_velocity_delta": float(feature_row.commit_velocity_delta),
        "issue_close_rate": float(feature_row.issue_close_rate),
        "bus_factor": float(feature_row.bus_factor),
        "maintainer_inactivity_days": float(feature_row.maintainer_inactivity_days),
        "news_sentiment_avg": float(feature_row.news_sentiment_avg),
        "days_since_last_release": float(feature_row.days_since_last_release),
    }


def _build_single_vector(feature_values: dict[str, float]) -> np.ndarray:
    ordered = [float(feature_values.get(name, 0.0)) for name in FEATURE_COLUMNS]
    return np.asarray([ordered], dtype=float)


def _normalize_top_features(raw_top_features: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_top_features, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in raw_top_features:
        if not isinstance(item, dict):
            continue
        feature = item.get("feature")
        shap_value = item.get("shap_value")
        direction = item.get("direction")
        if not isinstance(feature, str):
            continue
        if direction not in {"risk", "safe"}:
            direction = "safe"
        try:
            shap_float = float(shap_value)
        except (TypeError, ValueError):
            continue
        normalized.append({"feature": feature, "shap_value": shap_float, "direction": direction})
    return normalized


def score_project(session: Session, project_id: int) -> dict[str, Any]:
    """Score a project using latest features and persist the resulting risk score."""
    latest_feature = (
        session.execute(
            select(Feature)
            .where(Feature.project_id == project_id)
            .order_by(Feature.week_start.desc(), Feature.id.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )

    feature_values = _feature_row_to_dict(latest_feature)
    X_single = _build_single_vector(feature_values)

    if latest_feature is None:
        prediction = fallback_heuristic(feature_values)
    else:
        try:
            model = load_model(MODEL_PATH)
            prediction = predict_with_explanation(model, X_single, list(FEATURE_COLUMNS))
        except FileNotFoundError:
            prediction = fallback_heuristic(feature_values)
        except Exception:
            prediction = fallback_heuristic(feature_values)

    score = int(prediction.get("score", 0))
    score = max(0, min(100, score))
    top_features = _normalize_top_features(prediction.get("top_features", []))

    scored_at = _utc_now()
    upsert_window_start = scored_at - timedelta(days=6)
    feature_names = [item["feature"] for item in top_features[:3]]
    while len(feature_names) < 3:
        feature_names.append(None)

    existing_row = (
        session.execute(
            select(RiskScore)
            .where(
                RiskScore.project_id == project_id,
                RiskScore.scored_at >= upsert_window_start,
            )
            .order_by(RiskScore.scored_at.desc(), RiskScore.id.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )

    if existing_row is not None:
        existing_row.score = score
        existing_row.scored_at = scored_at
        existing_row.top_feature_1 = feature_names[0]
        existing_row.top_feature_2 = feature_names[1]
        existing_row.top_feature_3 = feature_names[2]
    else:
        risk_row = RiskScore(
            project_id=project_id,
            scored_at=scored_at,
            score=score,
            top_feature_1=feature_names[0],
            top_feature_2=feature_names[1],
            top_feature_3=feature_names[2],
        )
        session.add(risk_row)

    session.flush()

    return {
        "score": score,
        "top_features": top_features,
        "scored_at": scored_at,
        "project_id": project_id,
    }
