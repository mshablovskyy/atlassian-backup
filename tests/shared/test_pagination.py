"""Tests for shared.pagination module."""

from __future__ import annotations

import pytest
import responses

from atlassian_backup.shared.auth import BearerTokenAuth
from atlassian_backup.shared.http_client import create_session
from atlassian_backup.shared.pagination import paginated_get


class TestPaginatedGet:
    @responses.activate
    def test_single_page(self) -> None:
        responses.add(
            responses.GET,
            "https://example.com/api/content",
            json={"results": [{"id": "1"}, {"id": "2"}], "size": 2},
            status=200,
        )
        session = create_session(BearerTokenAuth("test"))
        results = list(paginated_get(session, "https://example.com/api/content", limit=25))
        assert len(results) == 2
        assert results[0]["id"] == "1"

    @responses.activate
    def test_multiple_pages(self) -> None:
        responses.add(
            responses.GET,
            "https://example.com/api/content",
            json={"results": [{"id": "1"}, {"id": "2"}], "size": 2},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://example.com/api/content",
            json={"results": [{"id": "3"}], "size": 1},
            status=200,
        )
        session = create_session(BearerTokenAuth("test"))
        results = list(paginated_get(session, "https://example.com/api/content", limit=2))
        assert len(results) == 3

    @responses.activate
    def test_empty_results(self) -> None:
        responses.add(
            responses.GET,
            "https://example.com/api/content",
            json={"results": [], "size": 0},
            status=200,
        )
        session = create_session(BearerTokenAuth("test"))
        results = list(paginated_get(session, "https://example.com/api/content"))
        assert results == []

    @responses.activate
    def test_error_response_raises(self) -> None:
        responses.add(
            responses.GET,
            "https://example.com/api/content",
            json={"message": "error"},
            status=500,
        )
        session = create_session(BearerTokenAuth("test"))
        with pytest.raises(RuntimeError, match="status 500"):
            list(paginated_get(session, "https://example.com/api/content"))
