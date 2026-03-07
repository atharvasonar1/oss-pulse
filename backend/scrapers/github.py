"""GitHub REST scraper for repository activity metrics."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from dotenv import load_dotenv

from backend.db.models import Project


class GitHubScraper:
    """Client wrapper for scraping GitHub repository metrics."""

    def __init__(self, token: str | None = None) -> None:
        load_dotenv()
        resolved_token = token or os.getenv("GITHUB_TOKEN")
        if not resolved_token:
            raise RuntimeError("GITHUB_TOKEN is not set. Define it in your environment or .env file.")

        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {resolved_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.max_retries = 3

    def _request(self, path: str, params: dict[str, Any] | None = None) -> requests.Response:
        """Request helper with exponential backoff for retryable status codes."""
        url = f"{self.base_url}{path}"
        for attempt in range(1, self.max_retries + 2):
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt <= self.max_retries:
                    time.sleep(2**attempt)
                    continue
            return response

        raise RuntimeError("Request failed after retry attempts.")

    @staticmethod
    def _since_iso8601(days: int) -> str:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        return since.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def get_contributor_stats(self, owner: str, repo: str) -> list[dict[str, Any]]:
        path = f"/repos/{owner}/{repo}/stats/contributors"
        for poll_attempt in range(1, 4):
            response = self._request(path)
            if response.status_code == 202:
                if poll_attempt < 3:
                    time.sleep(3)
                continue

            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, list) else []

        return []

    def get_commits(self, owner: str, repo: str, since_days: int = 90) -> list[dict[str, Any]]:
        path = f"/repos/{owner}/{repo}/commits"
        params = {"since": self._since_iso8601(since_days), "per_page": 100}
        response = self._request(path, params=params)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def get_issues(self, owner: str, repo: str, since_days: int = 90) -> list[dict[str, Any]]:
        path = f"/repos/{owner}/{repo}/issues"
        params = {"state": "all", "since": self._since_iso8601(since_days), "per_page": 100}
        response = self._request(path, params=params)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def get_releases(self, owner: str, repo: str) -> list[dict[str, Any]]:
        path = f"/repos/{owner}/{repo}/releases"
        params = {"per_page": 10}
        response = self._request(path, params=params)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def scrape_repo(self, owner: str, repo: str) -> dict[str, list[dict[str, Any]]]:
        return {
            "contributor_stats": self.get_contributor_stats(owner, repo),
            "commits": self.get_commits(owner, repo),
            "issues": self.get_issues(owner, repo),
            "releases": self.get_releases(owner, repo),
        }

    def scrape_all(self, projects: list[Project]) -> list[dict[str, list[dict[str, Any]]]]:
        return [self.scrape_repo(project.owner, project.repo) for project in projects]
