"""Google News RSS scraper with lightweight sentiment scoring."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree

import requests
import spacy
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import NewsItem


class NewsScraper:
    """Scrape project news from Google News RSS and persist sentiment-scored items."""

    POSITIVE_WORDS = {
        "good",
        "stable",
        "healthy",
        "improved",
        "strong",
        "active",
        "growing",
        "successful",
        "fixed",
        "resolved",
    }
    NEGATIVE_WORDS = {
        "abandoned",
        "broken",
        "vulnerable",
        "crisis",
        "deprecated",
        "inactive",
        "failing",
        "risk",
        "shortage",
        "critical",
        "unmaintained",
        "exploit",
        "backdoor",
    }

    def __init__(self) -> None:
        self.base_url = "https://news.google.com/rss/search"
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except Exception:
            self.nlp = spacy.blank("en")

    @staticmethod
    def _parse_pub_date(pub_date: str) -> datetime | None:
        try:
            parsed = parsedate_to_datetime(pub_date)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return None

    def fetch_articles(self, owner: str, repo: str) -> list[dict[str, Any]]:
        query = f"{owner} {repo} open source"
        params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        try:
            response = requests.get(self.base_url, params=params, timeout=20)
            response.raise_for_status()
            root = ElementTree.fromstring(response.text)
        except Exception:
            return []

        items = root.findall("./channel/item")
        articles: list[dict[str, Any]] = []
        for item in items:
            title = item.findtext("title", default="").strip()
            url = item.findtext("link", default="").strip()
            pub_date_raw = item.findtext("pubDate", default="").strip()
            source = item.findtext("source")
            source = source.strip() if source else None
            published_at = self._parse_pub_date(pub_date_raw)
            if not title or not url or published_at is None:
                continue
            if published_at < cutoff:
                continue

            articles.append(
                {
                    "title": title,
                    "url": url,
                    "published_at": published_at,
                    "source": source,
                }
            )

        return articles

    def score_sentiment(self, text: str) -> float:
        doc = self.nlp(text or "")
        words = [token.text.lower() for token in doc if token.is_alpha]
        total_words = len(words)
        positive_count = sum(1 for word in words if word in self.POSITIVE_WORDS)
        negative_count = sum(1 for word in words if word in self.NEGATIVE_WORDS)
        score = (positive_count - negative_count) / max(total_words, 1)
        return max(-1.0, min(1.0, score))

    def scrape_and_store(self, session: Session, project_id: int, owner: str, repo: str) -> int:
        articles = self.fetch_articles(owner, repo)
        inserted = 0

        for article in articles:
            url = article["url"]
            exists = session.execute(
                select(NewsItem).where(NewsItem.project_id == project_id, NewsItem.url == url).limit(1)
            ).scalar_one_or_none()
            if exists is not None:
                continue

            sentiment_score = self.score_sentiment(article["title"])
            session.add(
                NewsItem(
                    project_id=project_id,
                    title=article["title"],
                    url=url,
                    published_at=article["published_at"],
                    source=article["source"],
                    sentiment_score=sentiment_score,
                )
            )
            inserted += 1

        session.flush()
        return inserted
