from __future__ import annotations

from unittest.mock import Mock, patch

from backend.scrapers.libraries import fetch_dependent_count


def test_fetch_dependent_count_returns_zero_when_api_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("LIBRARIES_IO_API_KEY", raising=False)
    assert fetch_dependent_count("ansible", "ansible") == 0


def test_fetch_dependent_count_returns_zero_on_404(monkeypatch) -> None:
    monkeypatch.setenv("LIBRARIES_IO_API_KEY", "test-key")

    response = Mock()
    response.status_code = 404
    response.ok = False

    with patch("backend.scrapers.libraries.requests.get", return_value=response):
        assert fetch_dependent_count("ansible", "ansible") == 0


def test_fetch_dependent_count_returns_count_on_valid_response(monkeypatch) -> None:
    monkeypatch.setenv("LIBRARIES_IO_API_KEY", "test-key")

    response = Mock()
    response.status_code = 200
    response.ok = True
    response.json.return_value = {"dependents_count": 321}

    with patch("backend.scrapers.libraries.requests.get", return_value=response):
        assert fetch_dependent_count("ansible", "ansible") == 321
