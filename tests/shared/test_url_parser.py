"""Tests for shared.url_parser module."""

from __future__ import annotations

from atlassian_backup.shared.url_parser import extract_base_url


class TestExtractBaseUrl:
    def test_basic_url(self) -> None:
        assert extract_base_url("https://example.com/path/to/page") == "https://example.com"

    def test_url_with_port(self) -> None:
        assert extract_base_url("https://example.com:8443/path") == "https://example.com:8443"

    def test_url_with_query(self) -> None:
        result = extract_base_url("https://example.com/page?id=123")
        assert result == "https://example.com"
