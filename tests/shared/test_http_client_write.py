"""Tests for shared.http_client write support."""

from __future__ import annotations

import responses

from atlassian_backup.shared.auth import BearerTokenAuth
from atlassian_backup.shared.http_client import api_post, create_write_session


class TestCreateWriteSession:
    def test_session_has_auth(self) -> None:
        auth = BearerTokenAuth("test")
        session = create_write_session(auth)
        assert session.auth is auth

    def test_session_has_json_headers(self) -> None:
        auth = BearerTokenAuth("test")
        session = create_write_session(auth)
        assert session.headers["Accept"] == "application/json"

    def test_session_has_timeout(self) -> None:
        auth = BearerTokenAuth("test")
        session = create_write_session(auth, timeout=60)
        assert session.timeout == 60  # type: ignore[attr-defined]


class TestApiPost:
    @responses.activate
    def test_basic_post(self) -> None:
        responses.add(
            responses.POST,
            "https://example.com/api/test",
            json={"id": "123"},
            status=200,
        )
        auth = BearerTokenAuth("test")
        session = create_write_session(auth)
        resp = api_post(session, "https://example.com/api/test", json={"title": "Test"})
        assert resp.status_code == 200
        assert resp.json() == {"id": "123"}

    @responses.activate
    def test_post_with_headers(self) -> None:
        responses.add(
            responses.POST,
            "https://example.com/api/test",
            json={"ok": True},
            status=200,
        )
        auth = BearerTokenAuth("test")
        session = create_write_session(auth)
        resp = api_post(
            session,
            "https://example.com/api/test",
            json={"data": "value"},
            headers={"X-Custom": "header"},
        )
        assert resp.status_code == 200
