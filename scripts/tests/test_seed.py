from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.db.models import Base, Project
from scripts import seed


def _create_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def _mock_repo_response(name: str, description: str, html_url: str) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "name": name,
        "description": description,
        "html_url": html_url,
    }
    return response


def test_seed_inserts_new_project_correctly() -> None:
    session = _create_session()
    try:
        with patch("scripts.seed.requests.get") as mock_get:
            mock_get.return_value = _mock_repo_response(
                name="ansible",
                description="Automation tool",
                html_url="https://github.com/ansible/ansible",
            )

            summary = seed.seed_projects(session, ["ansible/ansible"], token="fake-token")
            session.commit()

        row = session.execute(select(Project).where(Project.owner == "ansible", Project.repo == "ansible")).scalar_one()
        assert row.name == "ansible"
        assert row.description == "Automation tool"
        assert row.html_url == "https://github.com/ansible/ansible"
        assert summary == {"inserted": 1, "already_existed": 0, "total": 1}
    finally:
        session.close()


def test_seed_is_idempotent_and_does_not_duplicate_projects() -> None:
    session = _create_session()
    try:
        with patch("scripts.seed.requests.get") as mock_get:
            mock_get.return_value = _mock_repo_response(
                name="podman",
                description="Container engine",
                html_url="https://github.com/containers/podman",
            )

            first = seed.seed_projects(session, ["containers/podman"], token=None)
            session.commit()
            second = seed.seed_projects(session, ["containers/podman"], token=None)
            session.commit()

        count = session.execute(select(Project)).scalars().all()
        assert len(count) == 1
        assert first == {"inserted": 1, "already_existed": 0, "total": 1}
        assert second == {"inserted": 0, "already_existed": 1, "total": 1}
    finally:
        session.close()


def test_parse_owner_repo_from_slug() -> None:
    owner, repo = seed.parse_repo_slug("ovn-org/ovn-kubernetes")
    assert owner == "ovn-org"
    assert repo == "ovn-kubernetes"


def test_fixture_json_files_valid_and_have_three_entries_minimum() -> None:
    fixtures_dir = Path("backend/scrapers/fixtures")
    files = [
        "contributor_stats.json",
        "commits.json",
        "issues.json",
        "releases.json",
    ]

    for filename in files:
        fixture_path = fixtures_dir / filename
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) >= 3
