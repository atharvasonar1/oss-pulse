from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.models import Base, Project


# backend.db.session requires DATABASE_URL at import time.
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


def test_get_health_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["version"] == "0.1.0"


def test_get_projects_empty_list_when_db_empty() -> None:
    session = _build_test_session()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get("/projects")

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["data"] == []
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_get_projects_returns_seeded_project_list() -> None:
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

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get("/projects")

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert len(payload["data"]) == 1
        assert payload["data"][0]["owner"] == "ansible"
        assert payload["data"][0]["repo"] == "ansible"
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_get_project_by_id_returns_project_when_exists() -> None:
    session = _build_test_session()
    project = Project(
        owner="cli",
        repo="cli",
        name="gh",
        description="GitHub CLI",
        html_url="https://github.com/cli/cli",
        created_at=datetime.now(timezone.utc),
    )
    session.add(project)
    session.commit()
    session.refresh(project)

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get(f"/projects/{project.id}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["data"]["id"] == project.id
        assert payload["data"]["owner"] == "cli"
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_get_project_by_id_returns_404_when_missing() -> None:
    session = _build_test_session()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get("/projects/9999")

        assert response.status_code == 404
        payload = response.json()
        assert payload["ok"] is False
        assert payload["error"] == "Project not found"
        assert payload["status"] == 404
    finally:
        app.dependency_overrides.clear()
        session.close()
