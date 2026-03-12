"""Tests for shared.auth module."""

from __future__ import annotations

from requests import PreparedRequest

from atlassian_backup.shared.auth import BearerTokenAuth


class TestBearerTokenAuth:
    def test_adds_bearer_header(self) -> None:
        auth = BearerTokenAuth("my-token")
        request = PreparedRequest()
        request.headers = {}  # type: ignore[assignment]
        result = auth(request)
        assert result.headers["Authorization"] == "Bearer my-token"

    def test_different_tokens(self) -> None:
        auth = BearerTokenAuth("token-abc")
        request = PreparedRequest()
        request.headers = {}  # type: ignore[assignment]
        auth(request)
        assert request.headers["Authorization"] == "Bearer token-abc"
