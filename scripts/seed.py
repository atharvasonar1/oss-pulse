"""Seed canonical OSS projects into the database."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable

import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from backend.db.models import Project


REPO_SLUG_PATTERN = re.compile(r"^\s*-\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\s*$")
GITHUB_API_VERSION = "2022-11-28"


def parse_repo_slug(repo_slug: str) -> tuple[str, str]:
    """Parse and validate a repo slug in owner/repo format."""
    if repo_slug.count("/") != 1:
        raise ValueError(f"Invalid repo slug '{repo_slug}'. Expected format owner/repo.")
    owner, repo = repo_slug.strip().split("/", 1)
    if not owner or not repo:
        raise ValueError(f"Invalid repo slug '{repo_slug}'. Expected format owner/repo.")
    return owner, repo


def load_repo_slugs(project_list_path: str | Path) -> list[str]:
    """Load repo slugs from docs/project-list.md bullet items."""
    path = Path(project_list_path)
    slugs: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = REPO_SLUG_PATTERN.match(line)
        if match:
            slugs.append(match.group(1))
    return slugs


def fetch_repo_metadata(owner: str, repo: str, token: str | None) -> dict[str, str | None]:
    """Fetch basic repo metadata from GitHub REST API."""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    payload = response.json()
    return {
        "name": payload.get("name"),
        "description": payload.get("description"),
        "html_url": payload.get("html_url"),
    }


def upsert_project(session: Session, owner: str, repo: str, metadata: dict[str, str | None]) -> str:
    """Insert project if missing, otherwise update metadata in place."""
    existing = session.query(Project).filter_by(owner=owner, repo=repo).one_or_none()
    if existing:
        existing.name = metadata.get("name") or repo
        existing.description = metadata.get("description")
        existing.html_url = metadata.get("html_url") or f"https://github.com/{owner}/{repo}"
        return "existing"

    project = Project(
        owner=owner,
        repo=repo,
        name=metadata.get("name") or repo,
        description=metadata.get("description"),
        html_url=metadata.get("html_url") or f"https://github.com/{owner}/{repo}",
    )
    session.add(project)
    return "inserted"


def seed_projects(session: Session, repo_slugs: Iterable[str], token: str | None) -> dict[str, int]:
    """Seed repo slugs into projects table and return summary counts."""
    inserted = 0
    already_existed = 0

    for repo_slug in repo_slugs:
        owner, repo = parse_repo_slug(repo_slug)
        metadata = fetch_repo_metadata(owner, repo, token=token)
        result = upsert_project(session, owner, repo, metadata)
        if result == "inserted":
            inserted += 1
        else:
            already_existed += 1

    session.flush()
    return {
        "inserted": inserted,
        "already_existed": already_existed,
        "total": inserted + already_existed,
    }


def run_seed(project_list_path: str | Path = "docs/project-list.md") -> dict[str, int]:
    """Run full seed flow using production DB session configuration."""
    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    slugs = load_repo_slugs(project_list_path)

    # Import lazily so tests can run without requiring DATABASE_URL at import time.
    from backend.db.session import get_session

    with get_session() as session:
        summary = seed_projects(session, slugs, token=token)

    return summary


def main() -> None:
    summary = run_seed()
    print(f"Inserted: {summary['inserted']}")
    print(f"Already existed: {summary['already_existed']}")
    print(f"Total processed: {summary['total']}")


if __name__ == "__main__":
    main()
