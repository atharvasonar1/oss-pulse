from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, Project, Snapshot
from backend.scrapers.github import GitHubScraper
from backend.scrapers.store import store_snapshot


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _load_fixture(name: str):
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _response(status_code: int, payload):
    mocked = MagicMock()
    mocked.status_code = status_code
    mocked.json.return_value = payload
    if status_code >= 400:
        mocked.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        mocked.raise_for_status.return_value = None
    return mocked


def test_scrape_repo_returns_expected_keys() -> None:
    contributor_stats = _load_fixture("contributor_stats.json")
    commits = _load_fixture("commits.json")
    issues = _load_fixture("issues.json")
    releases = _load_fixture("releases.json")

    scraper = GitHubScraper(token="test-token")
    with patch("backend.scrapers.github.requests.get") as mock_get:
        mock_get.side_effect = [
            _response(200, contributor_stats),
            _response(200, commits),
            _response(200, issues),
            _response(200, releases),
        ]
        payload = scraper.scrape_repo("ansible", "ansible")

    assert set(payload.keys()) == {"contributor_stats", "commits", "issues", "releases"}
    assert payload["contributor_stats"] == contributor_stats
    assert payload["commits"] == commits
    assert payload["issues"] == issues
    assert payload["releases"] == releases


def test_get_contributor_stats_handles_202_polling() -> None:
    contributor_stats = _load_fixture("contributor_stats.json")
    scraper = GitHubScraper(token="test-token")

    with patch("backend.scrapers.github.requests.get") as mock_get, patch("backend.scrapers.github.time.sleep") as mock_sleep:
        mock_get.side_effect = [
            _response(202, []),
            _response(200, contributor_stats),
        ]
        payload = scraper.get_contributor_stats("ansible", "ansible")

    assert payload == contributor_stats
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once_with(3)


def test_get_commits_includes_since_param() -> None:
    commits = _load_fixture("commits.json")
    scraper = GitHubScraper(token="test-token")

    with patch("backend.scrapers.github.requests.get") as mock_get:
        mock_get.return_value = _response(200, commits)
        payload = scraper.get_commits("ansible", "ansible", since_days=90)

    assert payload == commits
    called_params = mock_get.call_args.kwargs["params"]
    assert "since" in called_params
    assert called_params["since"].endswith("Z")
    assert called_params["per_page"] == 100


def test_store_snapshot_creates_snapshot_row() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with SessionLocal() as session:
        project = Project(
            owner="ansible",
            repo="ansible",
            name="ansible",
            description="Automation framework",
            html_url="https://github.com/ansible/ansible",
        )
        session.add(project)
        session.commit()
        session.refresh(project)

        raw_data = {
            "contributor_stats": _load_fixture("contributor_stats.json"),
            "commits": _load_fixture("commits.json"),
            "issues": _load_fixture("issues.json"),
            "releases": _load_fixture("releases.json"),
        }
        snapshot = store_snapshot(session, project.id, raw_data)
        session.commit()

        fetched = session.execute(select(Snapshot).where(Snapshot.id == snapshot.id)).scalar_one()
        assert fetched.project_id == project.id
        assert fetched.raw_json == raw_data


def test_scrape_all_calls_scrape_repo_per_project() -> None:
    scraper = GitHubScraper(token="test-token")
    projects = [
        Project(owner="ansible", repo="ansible", name="ansible", description=None, html_url="https://github.com/ansible/ansible"),
        Project(owner="cli", repo="cli", name="cli", description=None, html_url="https://github.com/cli/cli"),
    ]

    with patch.object(GitHubScraper, "scrape_repo", return_value={"contributor_stats": [], "commits": [], "issues": [], "releases": []}) as mock_scrape:
        result = scraper.scrape_all(projects)

    assert mock_scrape.call_count == len(projects)
    mock_scrape.assert_has_calls([call("ansible", "ansible"), call("cli", "cli")])
    assert len(result) == 2
