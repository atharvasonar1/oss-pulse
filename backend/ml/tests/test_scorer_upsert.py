from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.models import Base, Feature, Project, RiskScore
from backend.ml import scorer as scorer_module


def _build_test_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def _seed_project_with_feature(session: Session) -> Project:
    project = Project(
        owner="ansible",
        repo="ansible",
        name="ansible",
        description="Seed project",
        html_url="https://github.com/ansible/ansible",
        created_at=datetime.now(timezone.utc),
    )
    session.add(project)
    session.flush()

    feature = Feature(
        project_id=project.id,
        week_start=date(2026, 3, 23),
        contributor_delta_pct=-0.2,
        commit_velocity_delta=0.15,
        issue_close_rate=0.5,
        bus_factor=2,
        maintainer_inactivity_days=20,
        news_sentiment_avg=0.1,
        days_since_last_release=30,
    )
    session.add(feature)
    session.commit()
    session.refresh(project)
    return project


def test_score_project_twice_within_six_days_creates_one_row(monkeypatch) -> None:
    session = _build_test_session()
    project = _seed_project_with_feature(session)

    times = [
        datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc),
    ]
    predictions = iter(
        [
            {
                "score": 44,
                "top_features": [{"feature": "bus_factor", "shap_value": 0.3, "direction": "risk"}],
            },
            {
                "score": 68,
                "top_features": [{"feature": "issue_close_rate", "shap_value": 0.4, "direction": "risk"}],
            },
        ]
    )

    monkeypatch.setattr(scorer_module, "_utc_now", lambda: times.pop(0))
    monkeypatch.setattr(scorer_module, "load_model", lambda _path: object())
    monkeypatch.setattr(scorer_module, "predict_with_explanation", lambda *_args, **_kwargs: next(predictions))

    scorer_module.score_project(session, project.id)
    scorer_module.score_project(session, project.id)

    rows = session.execute(
        select(RiskScore).where(RiskScore.project_id == project.id).order_by(RiskScore.id.asc())
    ).scalars().all()

    assert len(rows) == 1
    assert rows[0].score == 68
    assert rows[0].top_feature_1 == "issue_close_rate"
    session.close()


def test_score_project_after_seven_days_creates_new_row(monkeypatch) -> None:
    session = _build_test_session()
    project = _seed_project_with_feature(session)

    t0 = datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc)
    times = [t0, t0 + timedelta(days=7)]
    predictions = iter(
        [
            {
                "score": 51,
                "top_features": [{"feature": "bus_factor", "shap_value": 0.2, "direction": "risk"}],
            },
            {
                "score": 59,
                "top_features": [{"feature": "commit_velocity_delta", "shap_value": 0.25, "direction": "risk"}],
            },
        ]
    )

    monkeypatch.setattr(scorer_module, "_utc_now", lambda: times.pop(0))
    monkeypatch.setattr(scorer_module, "load_model", lambda _path: object())
    monkeypatch.setattr(scorer_module, "predict_with_explanation", lambda *_args, **_kwargs: next(predictions))

    scorer_module.score_project(session, project.id)
    scorer_module.score_project(session, project.id)

    rows = session.execute(
        select(RiskScore).where(RiskScore.project_id == project.id).order_by(RiskScore.scored_at.asc(), RiskScore.id.asc())
    ).scalars().all()

    assert len(rows) == 2
    assert rows[0].score == 51
    assert rows[1].score == 59
    session.close()
