from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.db.models import Base, Feature, NewsItem, Project, Snapshot
from backend.pipeline import features as features_module
from backend.pipeline.features import extract_features


FIXED_NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
FIXED_TODAY = FIXED_NOW.date()
FIXED_WEEK_START = date(2026, 2, 23)


def _sqlite_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def _iso_days_ago(days: int) -> str:
    return (FIXED_NOW - timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _make_weeks(active_indices: set[int]) -> list[dict]:
    weeks = []
    for i in range(26):
        week_date = FIXED_TODAY - timedelta(days=(25 - i) * 7)
        week_dt = datetime.combine(week_date, datetime.min.time(), tzinfo=timezone.utc)
        weeks.append(
            {
                "w": int(week_dt.timestamp()),
                "a": 10,
                "d": 1,
                "c": 1 if i in active_indices else 0,
            }
        )
    return weeks


def _create_project(session: Session) -> Project:
    project = Project(
        owner="ansible",
        repo="ansible",
        name="ansible",
        description="Automation framework",
        html_url="https://github.com/ansible/ansible",
        created_at=FIXED_NOW,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def _create_snapshot(session: Session, project_id: int, raw_json: dict) -> Snapshot:
    snapshot = Snapshot(project_id=project_id, scraped_at=FIXED_NOW, raw_json=raw_json)
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return snapshot


@pytest.fixture(autouse=True)
def _fixed_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(features_module, "_utc_now", lambda: FIXED_NOW)
    monkeypatch.setattr(features_module, "_utc_today", lambda: FIXED_TODAY)


def test_contributor_delta_pct_negative_when_recent_lower() -> None:
    session = _sqlite_session()
    try:
        project = _create_project(session)
        raw_json = {
            "contributor_stats": [
                {"total": 90, "author": {"login": "a"}, "weeks": _make_weeks({8})},
                {"total": 80, "author": {"login": "b"}, "weeks": _make_weeks({10})},
                {"total": 70, "author": {"login": "c"}, "weeks": _make_weeks({9, 24})},
            ],
            "commits": [],
            "issues": [],
            "releases": [],
        }
        _create_snapshot(session, project.id, raw_json)

        feature = extract_features(session, project.id, FIXED_WEEK_START)
        session.commit()

        assert feature.contributor_delta_pct < 0
        assert feature.contributor_delta_pct == pytest.approx(-2 / 3, rel=1e-6)
    finally:
        session.close()


def test_commit_velocity_delta_positive_when_recent_outnumbers_previous() -> None:
    session = _sqlite_session()
    try:
        project = _create_project(session)
        raw_json = {
            "contributor_stats": [],
            "commits": [
                {"commit": {"author": {"date": _iso_days_ago(5)}}},
                {"commit": {"author": {"date": _iso_days_ago(12)}}},
                {"commit": {"author": {"date": _iso_days_ago(20)}}},
                {"commit": {"author": {"date": _iso_days_ago(60)}}},
            ],
            "issues": [],
            "releases": [],
        }
        _create_snapshot(session, project.id, raw_json)

        feature = extract_features(session, project.id, FIXED_WEEK_START)
        session.commit()

        assert feature.commit_velocity_delta > 0
        assert feature.commit_velocity_delta == pytest.approx(1.0, rel=1e-6)
    finally:
        session.close()


def test_issue_close_rate_ratio_is_correct() -> None:
    session = _sqlite_session()
    try:
        project = _create_project(session)
        raw_json = {
            "contributor_stats": [],
            "commits": [],
            "issues": [
                {"state": "closed"},
                {"state": "closed"},
                {"state": "open"},
            ],
            "releases": [],
        }
        _create_snapshot(session, project.id, raw_json)

        feature = extract_features(session, project.id, FIXED_WEEK_START)
        session.commit()

        assert feature.issue_close_rate == pytest.approx(2 / 3, rel=1e-6)
    finally:
        session.close()


def test_bus_factor_matches_expected_value() -> None:
    session = _sqlite_session()
    try:
        project = _create_project(session)
        raw_json = {
            "contributor_stats": [
                {"total": 40, "author": {"login": "a"}, "weeks": []},
                {"total": 35, "author": {"login": "b"}, "weeks": []},
                {"total": 25, "author": {"login": "c"}, "weeks": []},
            ],
            "commits": [],
            "issues": [],
            "releases": [],
        }
        _create_snapshot(session, project.id, raw_json)

        feature = extract_features(session, project.id, FIXED_WEEK_START)
        session.commit()

        assert feature.bus_factor == 2
    finally:
        session.close()


def test_maintainer_inactivity_days_returns_expected_max_for_top_three() -> None:
    session = _sqlite_session()
    try:
        project = _create_project(session)
        raw_json = {
            "contributor_stats": [
                {"total": 120, "author": {"login": "a"}, "weeks": _make_weeks({24})},
                {"total": 110, "author": {"login": "b"}, "weeks": _make_weeks({23})},
                {"total": 100, "author": {"login": "c"}, "weeks": _make_weeks({22})},
                {"total": 10, "author": {"login": "d"}, "weeks": _make_weeks({25})},
            ],
            "commits": [],
            "issues": [],
            "releases": [],
        }
        _create_snapshot(session, project.id, raw_json)

        feature = extract_features(session, project.id, FIXED_WEEK_START)
        session.commit()

        assert feature.maintainer_inactivity_days == 21
    finally:
        session.close()


def test_news_sentiment_avg_returns_mean_of_recent_items() -> None:
    session = _sqlite_session()
    try:
        project = _create_project(session)
        raw_json = {"contributor_stats": [], "commits": [], "issues": [], "releases": []}
        _create_snapshot(session, project.id, raw_json)

        news_rows = [
            NewsItem(
                project_id=project.id,
                title="Positive item",
                url="https://example.com/1",
                published_at=FIXED_NOW - timedelta(days=5),
                source="Test",
                sentiment_score=0.2,
            ),
            NewsItem(
                project_id=project.id,
                title="Another item",
                url="https://example.com/2",
                published_at=FIXED_NOW - timedelta(days=9),
                source="Test",
                sentiment_score=0.4,
            ),
            NewsItem(
                project_id=project.id,
                title="Mixed item",
                url="https://example.com/3",
                published_at=FIXED_NOW - timedelta(days=12),
                source="Test",
                sentiment_score=-0.1,
            ),
            NewsItem(
                project_id=project.id,
                title="Old item",
                url="https://example.com/old",
                published_at=FIXED_NOW - timedelta(days=45),
                source="Test",
                sentiment_score=0.9,
            ),
        ]
        session.add_all(news_rows)
        session.commit()

        feature = extract_features(session, project.id, FIXED_WEEK_START)
        session.commit()

        assert feature.news_sentiment_avg == pytest.approx((0.2 + 0.4 - 0.1) / 3, rel=1e-6)
    finally:
        session.close()


def test_days_since_last_release_returns_expected_days() -> None:
    session = _sqlite_session()
    try:
        project = _create_project(session)
        raw_json = {
            "contributor_stats": [],
            "commits": [],
            "issues": [],
            "releases": [
                {"tag_name": "v1.9.0", "published_at": "2025-11-15T12:00:00Z"},
                {"tag_name": "v1.10.0", "published_at": "2026-01-05T12:30:00Z"},
                {"tag_name": "v1.10.1", "published_at": "2026-02-14T08:45:00Z"},
            ],
        }
        _create_snapshot(session, project.id, raw_json)

        feature = extract_features(session, project.id, FIXED_WEEK_START)
        session.commit()

        assert feature.days_since_last_release == 15
    finally:
        session.close()


def test_extract_features_writes_all_seven_fields_to_features_table() -> None:
    session = _sqlite_session()
    try:
        project = _create_project(session)

        raw_json = {
            "contributor_stats": [
                {"total": 60, "author": {"login": "a"}, "weeks": _make_weeks({10, 24})},
                {"total": 30, "author": {"login": "b"}, "weeks": _make_weeks({8, 23})},
                {"total": 10, "author": {"login": "c"}, "weeks": _make_weeks({9, 22})},
                {"total": 5, "author": {"login": "d"}, "weeks": _make_weeks({9})},
                {"total": 4, "author": {"login": "e"}, "weeks": _make_weeks({21})},
            ],
            "commits": [
                {"commit": {"author": {"date": _iso_days_ago(5)}}},
                {"commit": {"author": {"date": _iso_days_ago(12)}}},
                {"commit": {"author": {"date": _iso_days_ago(20)}}},
                {"commit": {"author": {"date": _iso_days_ago(60)}}},
            ],
            "issues": [
                {"state": "closed"},
                {"state": "closed"},
                {"state": "open"},
            ],
            "releases": [
                {"tag_name": "v1.9.0", "published_at": "2025-11-15T12:00:00Z"},
                {"tag_name": "v1.10.0", "published_at": "2026-01-05T12:30:00Z"},
                {"tag_name": "v1.10.1", "published_at": "2026-02-14T08:45:00Z"},
            ],
        }
        _create_snapshot(session, project.id, raw_json)

        session.add_all(
            [
                NewsItem(
                    project_id=project.id,
                    title="Positive item",
                    url="https://example.com/n1",
                    published_at=FIXED_NOW - timedelta(days=5),
                    source="Test",
                    sentiment_score=0.5,
                ),
                NewsItem(
                    project_id=project.id,
                    title="Negative item",
                    url="https://example.com/n2",
                    published_at=FIXED_NOW - timedelta(days=8),
                    source="Test",
                    sentiment_score=-0.1,
                ),
            ]
        )
        session.commit()

        feature = extract_features(session, project.id, FIXED_WEEK_START)
        session.commit()

        persisted = session.execute(
            select(Feature).where(Feature.project_id == project.id, Feature.week_start == FIXED_WEEK_START)
        ).scalar_one()

        assert persisted.id == feature.id
        assert persisted.contributor_delta_pct == pytest.approx(0.0, abs=1e-6)
        assert persisted.commit_velocity_delta == pytest.approx(1.0, abs=1e-6)
        assert persisted.issue_close_rate == pytest.approx(2 / 3, rel=1e-6)
        assert persisted.bus_factor == 1
        assert persisted.maintainer_inactivity_days == 21
        assert persisted.news_sentiment_avg == pytest.approx(0.2, rel=1e-6)
        assert persisted.days_since_last_release == 15
    finally:
        session.close()
