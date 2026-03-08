from __future__ import annotations

import os
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.models import Base, Feature, Project, RiskScore
from backend.ml import scorer as scorer_module


# backend.db.session requires DATABASE_URL at import time.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
from backend.api.main import app, get_db  # noqa: E402


def _build_test_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def _seed_project(session: Session, owner: str = "ansible", repo: str = "ansible") -> Project:
    project = Project(
        owner=owner,
        repo=repo,
        name=repo,
        description="Seed project",
        html_url=f"https://github.com/{owner}/{repo}",
        created_at=datetime.now(timezone.utc),
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def _seed_feature(session: Session, project_id: int) -> Feature:
    feature = Feature(
        project_id=project_id,
        week_start=date(2026, 3, 2),
        contributor_delta_pct=-0.4,
        commit_velocity_delta=0.2,
        issue_close_rate=0.6,
        bus_factor=1,
        maintainer_inactivity_days=90,
        news_sentiment_avg=-0.2,
        days_since_last_release=70,
    )
    session.add(feature)
    session.commit()
    session.refresh(feature)
    return feature


def test_score_project_returns_expected_dict_shape(monkeypatch) -> None:
    session = _build_test_session()
    project = _seed_project(session)
    _seed_feature(session, project.id)

    monkeypatch.setattr(scorer_module, "load_model", lambda _path: object())
    monkeypatch.setattr(
        scorer_module,
        "predict_with_explanation",
        lambda _model, _x, _names: {
            "score": 74,
            "top_features": [
                {"feature": "bus_factor", "shap_value": 0.31, "direction": "risk"},
                {"feature": "news_sentiment_avg", "shap_value": -0.18, "direction": "safe"},
                {"feature": "issue_close_rate", "shap_value": -0.07, "direction": "safe"},
            ],
        },
    )

    result = scorer_module.score_project(session, project.id)
    assert set(result.keys()) == {"score", "top_features", "scored_at", "project_id"}
    assert result["score"] == 74
    assert result["project_id"] == project.id
    assert isinstance(result["top_features"], list)
    assert len(result["top_features"]) == 3
    assert isinstance(result["scored_at"], datetime)
    session.close()


def test_score_project_writes_risk_score_row_to_db(monkeypatch) -> None:
    session = _build_test_session()
    project = _seed_project(session, owner="cli", repo="cli")
    _seed_feature(session, project.id)

    monkeypatch.setattr(scorer_module, "load_model", lambda _path: object())
    monkeypatch.setattr(
        scorer_module,
        "predict_with_explanation",
        lambda _model, _x, _names: {
            "score": 61,
            "top_features": [
                {"feature": "contributor_delta_pct", "shap_value": 0.25, "direction": "risk"},
                {"feature": "maintainer_inactivity_days", "shap_value": 0.21, "direction": "risk"},
                {"feature": "bus_factor", "shap_value": 0.18, "direction": "risk"},
            ],
        },
    )

    scorer_module.score_project(session, project.id)

    risk_row = session.execute(
        select(RiskScore).where(RiskScore.project_id == project.id).order_by(RiskScore.id.desc())
    ).scalars().first()
    assert risk_row is not None
    assert risk_row.project_id == project.id
    assert risk_row.score == 61
    assert risk_row.top_feature_1 == "contributor_delta_pct"
    session.close()


def test_score_project_uses_fallback_when_model_missing(monkeypatch) -> None:
    session = _build_test_session()
    project = _seed_project(session, owner="rook", repo="rook")
    _seed_feature(session, project.id)

    def _raise_missing(_path: str):
        raise FileNotFoundError("missing model")

    monkeypatch.setattr(scorer_module, "load_model", _raise_missing)

    result = scorer_module.score_project(session, project.id)
    assert result["score"] == 100
    assert result["top_features"] == []
    session.close()


def test_get_project_risk_score_returns_200_shape(monkeypatch) -> None:
    session = _build_test_session()
    project = _seed_project(session, owner="prometheus", repo="prometheus")

    def override_get_db():
        try:
            yield session
        finally:
            pass

    monkeypatch.setattr(
        "backend.api.main.score_project",
        lambda _db, project_id: {
            "score": 68,
            "top_features": [
                {"feature": "bus_factor", "shap_value": 0.4, "direction": "risk"},
                {"feature": "maintainer_inactivity_days", "shap_value": 0.2, "direction": "risk"},
                {"feature": "news_sentiment_avg", "shap_value": -0.1, "direction": "safe"},
            ],
            "scored_at": datetime.now(timezone.utc),
            "project_id": project_id,
        },
    )

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get(f"/projects/{project.id}/risk-score")
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["project_id"] == project.id
    assert payload["data"]["score"] == 68
    assert len(payload["data"]["top_features"]) == 3


def test_get_project_risk_score_returns_404_when_project_missing() -> None:
    session = _build_test_session()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get("/projects/99999/risk-score")
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert response.status_code == 404
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "Project not found"
    assert payload["status"] == 404
