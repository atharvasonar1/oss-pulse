from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.db.models import Base, Feature, Project, Snapshot
from backend.pipeline.bus_factor import calculate_bus_factor
from backend.pipeline.extractor import extract_bus_factor_for_project


def _sqlite_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def _current_week_start_utc():
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=today.weekday())


def test_calculate_bus_factor_single_contributor_is_one() -> None:
    contributors = [{"total": 120, "author": {"login": "solo-maintainer"}}]
    assert calculate_bus_factor(contributors) == 1


def test_calculate_bus_factor_top_two_hit_exactly_fifty_percent() -> None:
    contributors = [
        {"total": 30, "author": {"login": "maintainer-a"}},
        {"total": 20, "author": {"login": "maintainer-b"}},
        {"total": 20, "author": {"login": "maintainer-c"}},
        {"total": 15, "author": {"login": "maintainer-d"}},
        {"total": 15, "author": {"login": "maintainer-e"}},
    ]
    assert calculate_bus_factor(contributors) == 2


def test_calculate_bus_factor_empty_list_returns_zero() -> None:
    assert calculate_bus_factor([]) == 0


def test_calculate_bus_factor_equal_share_contributors() -> None:
    contributors = [
        {"total": 10, "author": {"login": "a"}},
        {"total": 10, "author": {"login": "b"}},
        {"total": 10, "author": {"login": "c"}},
        {"total": 10, "author": {"login": "d"}},
    ]
    assert calculate_bus_factor(contributors) == 2


def test_extract_bus_factor_for_project_reads_snapshot_and_writes_feature() -> None:
    session = _sqlite_session()
    try:
        project = Project(
            owner="ansible",
            repo="ansible",
            name="ansible",
            description="Automation framework",
            html_url="https://github.com/ansible/ansible",
            created_at=datetime.now(timezone.utc),
        )
        session.add(project)
        session.commit()
        session.refresh(project)

        contributor_stats = [
            {"total": 60, "author": {"login": "a"}},
            {"total": 25, "author": {"login": "b"}},
            {"total": 15, "author": {"login": "c"}},
        ]
        snapshot = Snapshot(
            project_id=project.id,
            scraped_at=datetime.now(timezone.utc),
            raw_json={"contributor_stats": contributor_stats},
        )
        session.add(snapshot)
        session.commit()

        bus_factor = extract_bus_factor_for_project(session, project.id)
        session.commit()

        assert bus_factor == 1

        feature = session.execute(
            select(Feature).where(Feature.project_id == project.id, Feature.week_start == _current_week_start_utc())
        ).scalar_one()
        assert feature.project_id == project.id
        assert feature.week_start == _current_week_start_utc()
        assert feature.bus_factor == 1
    finally:
        session.close()
