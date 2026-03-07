from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.db.models import Base, Feature, NewsItem, Project, RiskScore, Snapshot


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _create_project(session: Session) -> Project:
    project = Project(
        owner="ansible",
        repo="ansible",
        name="Ansible",
        description="Automation platform",
        html_url="https://github.com/ansible/ansible",
        created_at=datetime.now(timezone.utc),
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def test_all_models_can_be_instantiated_without_errors() -> None:
    project = Project(
        owner="owner",
        repo="repo",
        name="name",
        description="desc",
        html_url="https://example.com",
        created_at=datetime.now(timezone.utc),
    )
    snapshot = Snapshot(project_id=1, scraped_at=datetime.now(timezone.utc), raw_json={"k": "v"})
    feature = Feature(
        project_id=1,
        week_start=date(2026, 1, 5),
        contributor_delta_pct=0.1,
        commit_velocity_delta=-0.2,
        issue_close_rate=0.75,
        bus_factor=2,
        maintainer_inactivity_days=7,
        news_sentiment_avg=0.05,
        days_since_last_release=15,
    )
    risk_score = RiskScore(
        project_id=1,
        scored_at=datetime.now(timezone.utc),
        score=42,
        top_feature_1="bus_factor",
        top_feature_2="issue_close_rate",
        top_feature_3="commit_velocity_delta",
    )
    news_item = NewsItem(
        project_id=1,
        title="Example title",
        url="https://example.com/news",
        published_at=datetime.now(timezone.utc),
        source="Example Source",
        sentiment_score=0.4,
    )

    assert project.name == "name"
    assert snapshot.raw_json == {"k": "v"}
    assert feature.bus_factor == 2
    assert risk_score.score == 42
    assert news_item.source == "Example Source"


def test_project_row_can_be_created_and_queried(db_session: Session) -> None:
    _create_project(db_session)

    fetched = db_session.query(Project).filter_by(owner="ansible", repo="ansible").one()
    assert fetched.name == "Ansible"
    assert fetched.html_url == "https://github.com/ansible/ansible"


def test_snapshot_linked_to_project_can_be_created_and_queried(db_session: Session) -> None:
    project = _create_project(db_session)
    snapshot = Snapshot(
        project_id=project.id,
        scraped_at=datetime.now(timezone.utc),
        raw_json={"commits": 10, "issues": 4},
    )
    db_session.add(snapshot)
    db_session.commit()

    fetched = db_session.query(Snapshot).filter_by(project_id=project.id).one()
    assert fetched.project_id == project.id
    assert fetched.raw_json["commits"] == 10


def test_feature_linked_to_project_can_be_created_and_queried(db_session: Session) -> None:
    project = _create_project(db_session)
    feature = Feature(
        project_id=project.id,
        week_start=date(2026, 1, 5),
        contributor_delta_pct=0.15,
        commit_velocity_delta=-0.1,
        issue_close_rate=0.68,
        bus_factor=3,
        maintainer_inactivity_days=5,
        news_sentiment_avg=0.12,
        days_since_last_release=9,
    )
    db_session.add(feature)
    db_session.commit()

    fetched = db_session.query(Feature).filter_by(project_id=project.id).one()
    assert fetched.week_start == date(2026, 1, 5)
    assert fetched.issue_close_rate == pytest.approx(0.68)


def test_risk_score_linked_to_project_can_be_created_and_queried(db_session: Session) -> None:
    project = _create_project(db_session)
    risk_score = RiskScore(
        project_id=project.id,
        scored_at=datetime.now(timezone.utc),
        score=77,
        top_feature_1="maintainer_inactivity_days",
        top_feature_2="days_since_last_release",
        top_feature_3="news_sentiment_avg",
    )
    db_session.add(risk_score)
    db_session.commit()

    fetched = db_session.query(RiskScore).filter_by(project_id=project.id).one()
    assert fetched.score == 77
    assert fetched.top_feature_1 == "maintainer_inactivity_days"


def test_news_item_linked_to_project_can_be_created_and_queried(db_session: Session) -> None:
    project = _create_project(db_session)
    news_item = NewsItem(
        project_id=project.id,
        title="Project reaches major milestone",
        url="https://example.com/project-news",
        published_at=datetime.now(timezone.utc),
        source="Tech Press",
        sentiment_score=0.9,
    )
    db_session.add(news_item)
    db_session.commit()

    fetched = db_session.query(NewsItem).filter_by(project_id=project.id).one()
    assert fetched.title == "Project reaches major milestone"
    assert fetched.sentiment_score == pytest.approx(0.9)
