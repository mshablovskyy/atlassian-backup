"""Tests for shared.http_client module."""

from __future__ import annotations

import responses

from atlassian_backup.shared.auth import BearerTokenAuth
from atlassian_backup.shared.http_client import api_get, create_session


class TestCreateSession:
    def test_session_has_auth(self) -> None:
        auth = BearerTokenAuth("test")
        session = create_session(auth)
        assert session.auth is auth

    def test_session_has_json_headers(self) -> None:
        auth = BearerTokenAuth("test")
        session = create_session(auth)
        assert session.headers["Accept"] == "application/json"

    def test_session_has_timeout(self) -> None:
        auth = BearerTokenAuth("test")
        session = create_session(auth, timeout=60)
        assert session.timeout == 60  # type: ignore[attr-defined]


class TestApiGet:
    @responses.activate
    def test_basic_get(self) -> None:
        responses.add(
            responses.GET,
            "https://example.com/api/test",
            json={"key": "value"},
            status=200,
        )
        auth = BearerTokenAuth("test")
        session = create_session(auth)
        resp = api_get(session, "https://example.com/api/test")
        assert resp.status_code == 200
        assert resp.json() == {"key": "value"}

    @responses.activate
    def test_get_with_params(self) -> None:
        responses.add(
            responses.GET,
            "https://example.com/api/test",
            json={"results": []},
            status=200,
        )
        auth = BearerTokenAuth("test")
        session = create_session(auth)
        resp = api_get(session, "https://example.com/api/test", params={"limit": 10})
        assert resp.status_code == 200
        assert "limit=10" in resp.url
