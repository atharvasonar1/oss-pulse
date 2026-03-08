from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.db.models import Base, NewsItem, Project
from backend.scrapers.news import NewsScraper


def _sqlite_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def _rss_xml(pub_dates: list[str]) -> str:
    return f"""
    <rss version="2.0">
      <channel>
        <title>News</title>
        <item>
          <title>Project is stable and active</title>
          <link>https://example.com/a1</link>
          <pubDate>{pub_dates[0]}</pubDate>
          <source url="https://source1.test">Source One</source>
        </item>
        <item>
          <title>Project fixed critical bug</title>
          <link>https://example.com/a2</link>
          <pubDate>{pub_dates[1]}</pubDate>
          <source url="https://source2.test">Source Two</source>
        </item>
        <item>
          <title>Maintainers resolved release issue</title>
          <link>https://example.com/a3</link>
          <pubDate>{pub_dates[2]}</pubDate>
          <source url="https://source3.test">Source Three</source>
        </item>
      </channel>
    </rss>
    """.strip()


def test_fetch_articles_returns_list_for_valid_xml() -> None:
    scraper = NewsScraper()
    now = datetime.now(timezone.utc)
    xml_text = _rss_xml(
        [
            (now - timedelta(days=2)).strftime("%a, %d %b %Y %H:%M:%S GMT"),
            (now - timedelta(days=4)).strftime("%a, %d %b %Y %H:%M:%S GMT"),
            (now - timedelta(days=8)).strftime("%a, %d %b %Y %H:%M:%S GMT"),
        ]
    )

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.text = xml_text

    with patch("backend.scrapers.news.requests.get", return_value=response):
        articles = scraper.fetch_articles("ansible", "ansible")

    assert len(articles) == 3
    assert articles[0]["title"] == "Project is stable and active"
    assert articles[0]["url"] == "https://example.com/a1"
    assert articles[0]["source"] == "Source One"
    assert isinstance(articles[0]["published_at"], datetime)


def test_fetch_articles_returns_empty_for_invalid_xml() -> None:
    scraper = NewsScraper()
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.text = "<rss><channel><item></channel>"

    with patch("backend.scrapers.news.requests.get", return_value=response):
        articles = scraper.fetch_articles("ansible", "ansible")

    assert articles == []


def test_score_sentiment_positive_text_returns_positive_value() -> None:
    scraper = NewsScraper()
    score = scraper.score_sentiment("Good stable healthy improved active project")
    assert score > 0


def test_score_sentiment_negative_text_returns_negative_value() -> None:
    scraper = NewsScraper()
    score = scraper.score_sentiment("Broken vulnerable inactive project with critical risk")
    assert score < 0


def test_scrape_and_store_inserts_and_skips_duplicates() -> None:
    session = _sqlite_session()
    try:
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

        scraper = NewsScraper()
        articles = [
            {
                "title": "Stable release resolved major issue",
                "url": "https://example.com/news-1",
                "published_at": datetime.now(timezone.utc) - timedelta(days=1),
                "source": "Source One",
            },
            {
                "title": "Project active and growing with strong adoption",
                "url": "https://example.com/news-2",
                "published_at": datetime.now(timezone.utc) - timedelta(days=3),
                "source": "Source Two",
            },
            {
                "title": "Critical risk fixed by maintainers",
                "url": "https://example.com/news-3",
                "published_at": datetime.now(timezone.utc) - timedelta(days=6),
                "source": "Source Three",
            },
        ]

        with patch.object(NewsScraper, "fetch_articles", return_value=articles):
            first_inserted = scraper.scrape_and_store(session, project.id, "ansible", "ansible")
            session.commit()
            second_inserted = scraper.scrape_and_store(session, project.id, "ansible", "ansible")
            session.commit()

        stored = session.execute(select(NewsItem).where(NewsItem.project_id == project.id)).scalars().all()
        assert first_inserted == 3
        assert second_inserted == 0
        assert len(stored) == 3
        assert {item.url for item in stored} == {
            "https://example.com/news-1",
            "https://example.com/news-2",
            "https://example.com/news-3",
        }
    finally:
        session.close()
