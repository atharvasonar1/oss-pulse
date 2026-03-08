"""Feature extraction logic for weekly project risk signals."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Feature, NewsItem, Snapshot
from backend.pipeline.bus_factor import calculate_bus_factor


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_today() -> date:
    return _utc_now().date()


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _extract_contributor_delta_pct(contributor_stats: list[dict[str, Any]]) -> float:
    recent_active: set[str] = set()
    previous_active: set[str] = set()

    for index, contributor in enumerate(contributor_stats):
        author = contributor.get("author", {}) if isinstance(contributor, dict) else {}
        login = author.get("login") if isinstance(author, dict) else None
        contributor_id = str(login) if login else f"contributor-{index}"

        weeks = contributor.get("weeks", []) if isinstance(contributor, dict) else []
        if not isinstance(weeks, list):
            continue

        normalized_weeks: list[dict[str, Any]] = [week for week in weeks if isinstance(week, dict)]
        normalized_weeks.sort(key=lambda week: int(week.get("w", 0)))

        recent_window = normalized_weeks[-13:]
        previous_window = normalized_weeks[-26:-13]

        if any(int(week.get("c", 0)) > 0 for week in recent_window):
            recent_active.add(contributor_id)
        if any(int(week.get("c", 0)) > 0 for week in previous_window):
            previous_active.add(contributor_id)

    recent_count = len(recent_active)
    previous_count = len(previous_active)
    delta = (recent_count - previous_count) / max(previous_count, 1)
    return _clamp(float(delta), -1.0, 1.0)


def _extract_commit_velocity_delta(commits: list[dict[str, Any]], now: datetime) -> float:
    recent_start = now - timedelta(days=45)
    previous_start = now - timedelta(days=90)

    recent_count = 0
    previous_count = 0

    for commit in commits:
        commit_data = commit.get("commit", {}) if isinstance(commit, dict) else {}
        author_data = commit_data.get("author", {}) if isinstance(commit_data, dict) else {}
        commit_date = _parse_iso_datetime(author_data.get("date") if isinstance(author_data, dict) else None)
        if commit_date is None:
            continue

        if recent_start <= commit_date <= now:
            recent_count += 1
        elif previous_start <= commit_date < recent_start:
            previous_count += 1

    delta = (recent_count - previous_count) / max(previous_count, 1)
    return _clamp(float(delta), -1.0, 1.0)


def _extract_issue_close_rate(issues: list[dict[str, Any]]) -> float:
    total_count = len(issues)
    closed_count = sum(1 for issue in issues if str(issue.get("state", "")).lower() == "closed")
    rate = closed_count / max(total_count, 1)
    return _clamp(float(rate), 0.0, 1.0)


def _extract_maintainer_inactivity_days(contributor_stats: list[dict[str, Any]], today: date) -> int:
    if not contributor_stats:
        return 0

    def _total(item: dict[str, Any]) -> int:
        return int(item.get("total", 0))

    top_maintainers = sorted(
        [item for item in contributor_stats if isinstance(item, dict)],
        key=_total,
        reverse=True,
    )[:3]

    inactivity_values: list[int] = []
    for maintainer in top_maintainers:
        weeks = maintainer.get("weeks", [])
        if not isinstance(weeks, list):
            continue
        active_weeks = [
            int(week.get("w", 0))
            for week in weeks
            if isinstance(week, dict) and int(week.get("c", 0)) > 0 and int(week.get("w", 0)) > 0
        ]
        if not active_weeks:
            continue

        most_recent_ts = max(active_weeks)
        active_date = datetime.fromtimestamp(most_recent_ts, tz=timezone.utc).date()
        inactivity_values.append(max(0, (today - active_date).days))

    return max(inactivity_values) if inactivity_values else 0


def _extract_news_sentiment_avg(session: Session, project_id: int, week_start: date) -> float:
    window_start = datetime.combine(week_start, time.min, tzinfo=timezone.utc) - timedelta(days=30)
    sentiment_scores = session.execute(
        select(NewsItem.sentiment_score).where(
            NewsItem.project_id == project_id,
            NewsItem.published_at >= window_start,
        )
    ).scalars().all()
    if not sentiment_scores:
        return 0.0
    return float(sum(sentiment_scores) / len(sentiment_scores))


def _extract_days_since_last_release(releases: list[dict[str, Any]], today: date) -> int:
    release_datetimes: list[datetime] = []
    for release in releases:
        published_at = _parse_iso_datetime(release.get("published_at") if isinstance(release, dict) else None)
        if published_at is not None:
            release_datetimes.append(published_at)

    if not release_datetimes:
        return 365

    most_recent_release = max(release_datetimes).date()
    return max(0, (today - most_recent_release).days)


def extract_features(session: Session, project_id: int, week_start: date) -> Feature:
    """Compute and upsert all seven feature columns for one project/week."""
    latest_snapshot = session.execute(
        select(Snapshot)
        .where(Snapshot.project_id == project_id)
        .order_by(Snapshot.scraped_at.desc(), Snapshot.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    raw_json = latest_snapshot.raw_json if latest_snapshot and isinstance(latest_snapshot.raw_json, dict) else {}
    contributor_stats = raw_json.get("contributor_stats", [])
    commits = raw_json.get("commits", [])
    issues = raw_json.get("issues", [])
    releases = raw_json.get("releases", [])

    contributor_stats = contributor_stats if isinstance(contributor_stats, list) else []
    commits = commits if isinstance(commits, list) else []
    issues = issues if isinstance(issues, list) else []
    releases = releases if isinstance(releases, list) else []

    now = _utc_now()
    today = _utc_today()

    contributor_delta_pct = _extract_contributor_delta_pct(contributor_stats)
    commit_velocity_delta = _extract_commit_velocity_delta(commits, now)
    issue_close_rate = _extract_issue_close_rate(issues)
    bus_factor = calculate_bus_factor(contributor_stats)
    maintainer_inactivity_days = _extract_maintainer_inactivity_days(contributor_stats, today)
    news_sentiment_avg = _extract_news_sentiment_avg(session, project_id, week_start)
    days_since_last_release = _extract_days_since_last_release(releases, today)

    feature = session.execute(
        select(Feature).where(Feature.project_id == project_id, Feature.week_start == week_start).limit(1)
    ).scalar_one_or_none()

    if feature is None:
        feature = Feature(project_id=project_id, week_start=week_start)
        session.add(feature)

    feature.contributor_delta_pct = contributor_delta_pct
    feature.commit_velocity_delta = commit_velocity_delta
    feature.issue_close_rate = issue_close_rate
    feature.bus_factor = bus_factor
    feature.maintainer_inactivity_days = maintainer_inactivity_days
    feature.news_sentiment_avg = news_sentiment_avg
    feature.days_since_last_release = days_since_last_release

    session.flush()
    session.refresh(feature)
    return feature
