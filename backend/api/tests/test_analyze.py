from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.models import Base, Project, RiskScore
from backend.parsers.manifest import parse_go_mod, parse_package_json, parse_requirements_txt


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


def test_parse_requirements_txt_strips_version_specifiers() -> None:
    content = """
    requests>=2.28.0
    pandas==2.1.1
    fastapi[all]~=0.116.0
    """
    packages = parse_requirements_txt(content)
    assert packages == ["requests", "pandas", "fastapi"]


def test_parse_package_json_reads_dependencies_keys() -> None:
    content = """
    {
      "dependencies": { "react": "^18.3.1", "recharts": "^2.12.7" },
      "devDependencies": { "vitest": "^2.1.9" }
    }
    """
    packages = parse_package_json(content)
    assert packages == ["react", "recharts", "vitest"]


def test_parse_go_mod_reads_require_block() -> None:
    content = """
    module github.com/example/app

    require (
      github.com/gin-gonic/gin v1.10.0
      golang.org/x/net v0.35.0
    )
    """
    packages = parse_go_mod(content)
    assert packages == ["github.com/gin-gonic/gin", "golang.org/x/net"]


def test_post_analyze_returns_ok_shape() -> None:
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
    session.add(
        RiskScore(
            project_id=project.id,
            score=71,
            top_feature_1="bus_factor",
            top_feature_2="maintainer_inactivity_days",
            top_feature_3=None,
            scored_at=datetime.now(timezone.utc),
        )
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
            response = client.post(
                "/analyze",
                files={"file": ("requirements.txt", b"ansible>=9.0.0\nunknownlib==1.0.0\n", "text/plain")},
            )
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "matched" in payload["data"]
    assert "unmatched" in payload["data"]
    assert isinstance(payload["data"]["matched"], list)
    assert isinstance(payload["data"]["unmatched"], list)
