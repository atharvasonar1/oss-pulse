"""Weekly pipeline scheduler and manual trigger entrypoints."""

from __future__ import annotations

from datetime import date, datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import select

from backend.db.models import Project
from backend.pipeline.features import extract_features
from backend.scrapers.github import GitHubScraper
from backend.scrapers.news import NewsScraper
from backend.scrapers.store import store_snapshot


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_today() -> date:
    return _utc_now().date()


def _current_week_start_utc() -> date:
    today = _utc_today()
    return today.fromordinal(today.toordinal() - today.weekday())


def run_pipeline() -> int:
    """Run scrape -> news -> feature extraction pipeline for all projects."""
    started_at = _utc_now()
    print(f"Pipeline start: {started_at.isoformat()}")

    # Import lazily to avoid import-time DATABASE_URL dependency in tests.
    from backend.db.session import get_session

    with get_session() as session:
        projects = session.execute(select(Project).order_by(Project.id.asc())).scalars().all()
        total_projects = len(projects)

        github_scraper = GitHubScraper()
        news_scraper = NewsScraper()
        week_start = _current_week_start_utc()

        for project in projects:
            repo_id = f"{project.owner}/{project.repo}"
            try:
                raw_data = github_scraper.scrape_repo(project.owner, project.repo)
                snapshot = store_snapshot(session, project.id, raw_data)
                print(f"Scraped {repo_id} — snapshot id {snapshot.id}")
            except Exception as exc:
                print(f"Scrape failed for {repo_id}: {exc}")
                continue

            try:
                inserted_count = news_scraper.scrape_and_store(session, project.id, project.owner, project.repo)
                print(f"News scraped for {repo_id} — {inserted_count} new articles")
            except Exception as exc:
                print(f"News scrape failed for {repo_id}: {exc}")

            try:
                extract_features(session, project.id, week_start)
                print(f"Features extracted for {repo_id}")
            except Exception as exc:
                print(f"Feature extraction failed for {repo_id}: {exc}")

        print("Model inference placeholder — to be wired in PH4")

    ended_at = _utc_now()
    print(f"Pipeline end: {ended_at.isoformat()}")
    print(f"Total projects processed: {total_projects}")
    return total_projects


def start_scheduler() -> BackgroundScheduler:
    """Start a background scheduler for integration with FastAPI process."""
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_pipeline,
        "cron",
        day_of_week="mon",
        hour=3,
        minute=0,
        id="weekly_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler


def start_blocking_scheduler() -> BlockingScheduler:
    """Start a blocking scheduler for standalone worker execution."""
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_pipeline,
        "cron",
        day_of_week="mon",
        hour=3,
        minute=0,
        id="weekly_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler


def trigger_now() -> int:
    """Run pipeline immediately in current thread."""
    return run_pipeline()
