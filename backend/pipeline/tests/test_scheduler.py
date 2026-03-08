from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, call, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.db.models import Base, Project
from backend.pipeline import scheduler as scheduler_module
from backend.pipeline.scheduler import run_pipeline


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
from backend.api.main import app  # noqa: E402


def _sqlite_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def _seed_projects(session: Session) -> list[Project]:
    rows = [
        Project(
            owner="ansible",
            repo="ansible",
            name="ansible",
            description="Automation",
            html_url="https://github.com/ansible/ansible",
            created_at=datetime.now(timezone.utc),
        ),
        Project(
            owner="cli",
            repo="cli",
            name="cli",
            description="GitHub CLI",
            html_url="https://github.com/cli/cli",
            created_at=datetime.now(timezone.utc),
        ),
        Project(
            owner="rook",
            repo="rook",
            name="rook",
            description="Storage orchestration",
            html_url="https://github.com/rook/rook",
            created_at=datetime.now(timezone.utc),
        ),
    ]
    session.add_all(rows)
    session.commit()
    for row in rows:
        session.refresh(row)
    return rows


def _session_ctx(session: Session):
    @contextmanager
    def _ctx():
        yield session

    return _ctx


def test_run_pipeline_calls_scrape_repo_once_per_project() -> None:
    session = _sqlite_session()
    projects = _seed_projects(session)
    week_start = date(2026, 3, 2)

    with (
        patch("backend.db.session.get_session", _session_ctx(session)),
        patch("backend.pipeline.scheduler.GitHubScraper") as mock_github_cls,
        patch("backend.pipeline.scheduler.NewsScraper") as mock_news_cls,
        patch("backend.pipeline.scheduler.store_snapshot") as mock_store_snapshot,
        patch("backend.pipeline.scheduler.extract_features") as mock_extract_features,
        patch.object(scheduler_module, "_current_week_start_utc", return_value=week_start),
    ):
        mock_github = mock_github_cls.return_value
        mock_github.scrape_repo.return_value = {"contributor_stats": [], "commits": [], "issues": [], "releases": []}
        mock_news_cls.return_value.scrape_and_store.return_value = 0
        mock_store_snapshot.side_effect = [MagicMock(id=1), MagicMock(id=2), MagicMock(id=3)]

        processed = run_pipeline()

    assert processed == len(projects)
    assert mock_github.scrape_repo.call_count == len(projects)
    assert mock_github.scrape_repo.call_args_list == [
        call("ansible", "ansible"),
        call("cli", "cli"),
        call("rook", "rook"),
    ]
    assert mock_extract_features.call_count == len(projects)
    session.close()


def test_run_pipeline_calls_scrape_and_store_once_per_project() -> None:
    session = _sqlite_session()
    _seed_projects(session)
    week_start = date(2026, 3, 2)

    with (
        patch("backend.db.session.get_session", _session_ctx(session)),
        patch("backend.pipeline.scheduler.GitHubScraper") as mock_github_cls,
        patch("backend.pipeline.scheduler.NewsScraper") as mock_news_cls,
        patch("backend.pipeline.scheduler.store_snapshot") as mock_store_snapshot,
        patch("backend.pipeline.scheduler.extract_features"),
        patch.object(scheduler_module, "_current_week_start_utc", return_value=week_start),
    ):
        mock_github_cls.return_value.scrape_repo.return_value = {
            "contributor_stats": [],
            "commits": [],
            "issues": [],
            "releases": [],
        }
        mock_news = mock_news_cls.return_value
        mock_news.scrape_and_store.return_value = 2
        mock_store_snapshot.side_effect = [MagicMock(id=1), MagicMock(id=2), MagicMock(id=3)]

        run_pipeline()

    assert mock_news.scrape_and_store.call_count == 3
    session.close()


def test_run_pipeline_calls_extract_features_with_week_start() -> None:
    session = _sqlite_session()
    projects = _seed_projects(session)
    week_start = date(2026, 3, 2)

    with (
        patch("backend.db.session.get_session", _session_ctx(session)),
        patch("backend.pipeline.scheduler.GitHubScraper") as mock_github_cls,
        patch("backend.pipeline.scheduler.NewsScraper") as mock_news_cls,
        patch("backend.pipeline.scheduler.store_snapshot") as mock_store_snapshot,
        patch("backend.pipeline.scheduler.extract_features") as mock_extract_features,
        patch.object(scheduler_module, "_current_week_start_utc", return_value=week_start),
    ):
        mock_github_cls.return_value.scrape_repo.return_value = {
            "contributor_stats": [],
            "commits": [],
            "issues": [],
            "releases": [],
        }
        mock_news_cls.return_value.scrape_and_store.return_value = 0
        mock_store_snapshot.side_effect = [MagicMock(id=1), MagicMock(id=2), MagicMock(id=3)]

        run_pipeline()

    assert mock_extract_features.call_count == 3
    assert mock_extract_features.call_args_list == [
        call(session, projects[0].id, week_start),
        call(session, projects[1].id, week_start),
        call(session, projects[2].id, week_start),
    ]
    session.close()


def test_run_pipeline_continues_when_one_project_fails() -> None:
    session = _sqlite_session()
    projects = _seed_projects(session)
    week_start = date(2026, 3, 2)

    def scrape_side_effect(owner: str, repo: str):
        if owner == "cli":
            raise RuntimeError("simulated scrape failure")
        return {"contributor_stats": [], "commits": [], "issues": [], "releases": []}

    with (
        patch("backend.db.session.get_session", _session_ctx(session)),
        patch("backend.pipeline.scheduler.GitHubScraper") as mock_github_cls,
        patch("backend.pipeline.scheduler.NewsScraper") as mock_news_cls,
        patch("backend.pipeline.scheduler.store_snapshot") as mock_store_snapshot,
        patch("backend.pipeline.scheduler.extract_features") as mock_extract_features,
        patch.object(scheduler_module, "_current_week_start_utc", return_value=week_start),
    ):
        mock_github = mock_github_cls.return_value
        mock_github.scrape_repo.side_effect = scrape_side_effect
        mock_news_cls.return_value.scrape_and_store.return_value = 1
        mock_store_snapshot.side_effect = [MagicMock(id=1), MagicMock(id=2)]

        processed = run_pipeline()

    assert processed == len(projects)
    assert mock_github.scrape_repo.call_count == 3
    assert mock_news_cls.return_value.scrape_and_store.call_count == 2
    assert mock_extract_features.call_count == 2
    session.close()


def test_post_pipeline_trigger_returns_ok_shape() -> None:
    with patch("backend.api.main.trigger_now", return_value=7):
        with TestClient(app) as client:
            response = client.post("/pipeline/trigger")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["message"] == "Pipeline triggered"
    assert payload["data"]["projects_processed"] == 7
