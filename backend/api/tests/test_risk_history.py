from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.models import Base, Project, RiskScore


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


def test_get_risk_history_returns_ok_shape() -> None:
    session = _build_test_session()
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

    now = datetime.now(timezone.utc)
    session.add_all(
        [
            RiskScore(project_id=project.id, score=44, scored_at=now - timedelta(days=14)),
            RiskScore(project_id=project.id, score=58, scored_at=now - timedelta(days=7)),
            RiskScore(project_id=project.id, score=63, scored_at=now),
        ]
    )
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get(f"/projects/{project.id}/risk-history")
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert isinstance(payload["data"], list)
    assert len(payload["data"]) == 3
    assert payload["data"][0]["score"] == 44
    assert payload["data"][1]["score"] == 58
    assert payload["data"][2]["score"] == 63
