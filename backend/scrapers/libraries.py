"""libraries.io dependent count ingestion helpers."""

from __future__ import annotations

import os
from typing import Any

import requests


BASE_URL = "https://libraries.io/api"


def _platform_candidates(repo: str) -> list[str]:
    repo_lower = (repo or "").lower()
    js_hints = ("js", "node", "react", "vue", "angular", "webpack", "next")
    if any(hint in repo_lower for hint in js_hints):
        return ["npm", "github"]
    return ["pypi", "github"]


def _build_name(platform: str, owner: str, repo: str) -> str:
    if platform == "github":
        return f"{owner}/{repo}"
    return repo


def fetch_dependent_count(owner: str, repo: str) -> int:
    """Fetch dependents_count from libraries.io and return 0 on any failure."""
    api_key = os.getenv("LIBRARIES_IO_API_KEY")
    if not api_key:
        return 0

    for platform in _platform_candidates(repo):
        name = _build_name(platform, owner, repo)
        url = f"{BASE_URL}/{platform}/{name}"
        try:
            response = requests.get(url, params={"api_key": api_key}, timeout=15)
        except Exception:
            continue

        if response.status_code == 404:
            continue
        if not response.ok:
            continue

        try:
            payload: Any = response.json()
        except Exception:
            continue

        try:
            return int(payload.get("dependents_count", 0))
        except Exception:
            return 0

    return 0
