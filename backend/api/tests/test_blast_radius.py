from __future__ import annotations

import importlib.util
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.models import Base, Project


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


def test_get_projects_includes_dependent_count_field() -> None:
    session = _build_test_session()
    project = Project(
        owner="ansible",
        repo="ansible",
        name="ansible",
        description="Automation framework",
        html_url="https://github.com/ansible/ansible",
        dependent_count=1234,
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
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert len(payload["data"]) == 1
    assert payload["data"][0]["dependent_count"] == 1234


def test_alembic_migration_upgrade_and_downgrade_cleanly() -> None:
    migration_path = (
        Path.cwd() / "alembic" / "versions" / "20260314_0002_add_dependent_count_to_projects.py"
    )
    spec = importlib.util.spec_from_file_location("blast_radius_migration", migration_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE projects (
                    id INTEGER PRIMARY KEY,
                    owner VARCHAR(255) NOT NULL,
                    repo VARCHAR(255) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    html_url TEXT NOT NULL,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )

        context = MigrationContext.configure(connection)
        operations = Operations(context)
        original_op = module.op
        module.op = operations
        try:
            module.upgrade()
            columns_after_upgrade = {column["name"] for column in inspect(connection).get_columns("projects")}
            assert "dependent_count" in columns_after_upgrade

            module.downgrade()
            columns_after_downgrade = {column["name"] for column in inspect(connection).get_columns("projects")}
            assert "dependent_count" not in columns_after_downgrade
        finally:
            module.op = original_op
