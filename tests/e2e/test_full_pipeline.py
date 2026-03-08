from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.models import Base, Feature, Project, RiskScore, Snapshot
from backend.ml.scorer import score_project
from backend.pipeline.features import extract_features
from backend.scrapers.store import store_snapshot


# backend.db.session requires DATABASE_URL at import time.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
from backend.api.main import app, get_db  # noqa: E402


FIXTURES_DIR = Path("backend/scrapers/fixtures")


def _load_json_fixture(name: str):
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def project_row(db_session: Session) -> Project:
    project = Project(
        owner="ansible",
        repo="ansible",
        name="ansible",
        description="Automation framework",
        html_url="https://github.com/ansible/ansible",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture()
def raw_fixture_data() -> dict:
    return {
        "contributor_stats": _load_json_fixture("contributor_stats.json"),
        "commits": _load_json_fixture("commits.json"),
        "issues": _load_json_fixture("issues.json"),
        "releases": _load_json_fixture("releases.json"),
    }


@pytest.fixture()
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _session_ctx(session: Session):
    @contextmanager
    def _ctx():
        yield session

    return _ctx


def _seed_feature_via_extractor(db_session: Session, project_id: int, raw_data: dict) -> Feature:
    store_snapshot(db_session, project_id, raw_data)
    feature = extract_features(db_session, project_id, date(2026, 3, 3))
    db_session.commit()
    db_session.refresh(feature)
    return feature


def test_seed_and_scrape(db_session: Session, project_row: Project, raw_fixture_data: dict) -> None:
    scraper = MagicMock()
    scraper.scrape_repo.return_value = raw_fixture_data

    payload = scraper.scrape_repo("ansible", "ansible")
    snapshot = store_snapshot(db_session, project_row.id, payload)
    db_session.commit()

    stored = db_session.execute(
        select(Snapshot).where(Snapshot.project_id == project_row.id, Snapshot.id == snapshot.id)
    ).scalar_one_or_none()

    assert stored is not None
    assert stored.project_id == project_row.id
    assert isinstance(stored.raw_json, dict)
    assert set(stored.raw_json.keys()) == {"contributor_stats", "commits", "issues", "releases"}
    scraper.scrape_repo.assert_called_once_with("ansible", "ansible")


def test_feature_extraction(db_session: Session, project_row: Project, raw_fixture_data: dict) -> None:
    store_snapshot(db_session, project_row.id, raw_fixture_data)
    feature = extract_features(db_session, project_row.id, date(2026, 3, 3))
    db_session.commit()

    stored = db_session.execute(
        select(Feature).where(Feature.project_id == project_row.id, Feature.id == feature.id)
    ).scalar_one_or_none()

    assert stored is not None
    assert stored.contributor_delta_pct is not None
    assert stored.commit_velocity_delta is not None
    assert stored.issue_close_rate is not None
    assert stored.bus_factor is not None
    assert stored.maintainer_inactivity_days is not None
    assert stored.news_sentiment_avg is not None
    assert stored.days_since_last_release is not None


def test_risk_scoring(db_session: Session, project_row: Project, raw_fixture_data: dict) -> None:
    _seed_feature_via_extractor(db_session, project_row.id, raw_fixture_data)

    def _raise_missing(_path: str):
        raise FileNotFoundError("missing model")

    with patch("backend.ml.scorer.load_model", side_effect=_raise_missing):
        scored = score_project(db_session, project_row.id)
        db_session.commit()

    risk = db_session.execute(
        select(RiskScore).where(RiskScore.project_id == project_row.id).order_by(RiskScore.id.desc())
    ).scalars().first()

    assert risk is not None
    assert scored["project_id"] == project_row.id
    assert isinstance(scored["score"], int)
    assert 0 <= scored["score"] <= 100
    assert 0 <= risk.score <= 100


def test_api_projects(client: TestClient, project_row: Project) -> None:
    response = client.get("/projects")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert any(item["owner"] == "ansible" and item["repo"] == "ansible" for item in payload["data"])


def test_api_risk_score(
    client: TestClient, db_session: Session, project_row: Project, raw_fixture_data: dict
) -> None:
    _seed_feature_via_extractor(db_session, project_row.id, raw_fixture_data)

    def _raise_missing(_path: str):
        raise FileNotFoundError("missing model")

    with patch("backend.ml.scorer.load_model", side_effect=_raise_missing):
        response = client.get(f"/projects/{project_row.id}/risk-score")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["project_id"] == project_row.id
    assert isinstance(payload["data"]["score"], int)
    assert 0 <= payload["data"]["score"] <= 100
    assert isinstance(payload["data"]["top_features"], list)


def test_full_pipeline_trigger(
    client: TestClient, db_session: Session, project_row: Project, raw_fixture_data: dict
) -> None:
    with (
        patch("backend.db.session.get_session", _session_ctx(db_session)),
        patch("backend.pipeline.scheduler.GitHubScraper") as mock_github_cls,
        patch("backend.pipeline.scheduler.NewsScraper") as mock_news_cls,
        patch("backend.ml.scorer.load_model", side_effect=FileNotFoundError("missing model")),
    ):
        mock_github = mock_github_cls.return_value
        mock_github.scrape_repo.return_value = raw_fixture_data

        mock_news = mock_news_cls.return_value
        mock_news.scrape_and_store.return_value = 2

        response = client.post("/pipeline/trigger")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["message"] == "Pipeline triggered"
    assert payload["data"]["projects_processed"] >= 1

    assert mock_github.scrape_repo.call_count >= 1
    assert mock_news.scrape_and_store.call_count >= 1

    risk_rows = db_session.execute(select(RiskScore).where(RiskScore.project_id == project_row.id)).scalars().all()
    assert len(risk_rows) >= 1
