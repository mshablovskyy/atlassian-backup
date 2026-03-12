"""Tests for confluence.url_parser module."""

from __future__ import annotations

import pytest

from atlassian_backup.confluence.url_parser import ParsedConfluenceUrl, parse_confluence_url


class TestParseConfluenceUrl:
    def test_display_space(self) -> None:
        result = parse_confluence_url("https://confluence.example.com/display/MYSPACE")
        assert result == ParsedConfluenceUrl(target_type="space", space_key="MYSPACE")

    def test_display_space_trailing_slash(self) -> None:
        result = parse_confluence_url("https://confluence.example.com/display/MYSPACE/")
        assert result == ParsedConfluenceUrl(target_type="space", space_key="MYSPACE")

    def test_spaces_url(self) -> None:
        result = parse_confluence_url("https://confluence.example.com/spaces/DEV")
        assert result == ParsedConfluenceUrl(target_type="space", space_key="DEV")

    def test_spaces_overview(self) -> None:
        result = parse_confluence_url("https://confluence.example.com/spaces/DEV/overview")
        assert result == ParsedConfluenceUrl(target_type="space", space_key="DEV")

    def test_display_page_with_title(self) -> None:
        result = parse_confluence_url("https://confluence.example.com/display/MYSPACE/My+Page")
        assert result == ParsedConfluenceUrl(
            target_type="page", space_key="MYSPACE", page_title="My+Page"
        )

    def test_viewpage_action(self) -> None:
        result = parse_confluence_url(
            "https://confluence.example.com/pages/viewpage.action?pageId=12345"
        )
        assert result == ParsedConfluenceUrl(target_type="page", page_id="12345")

    def test_spaces_pages_with_id(self) -> None:
        result = parse_confluence_url(
            "https://confluence.example.com/spaces/DEV/pages/67890/My-Title"
        )
        assert result == ParsedConfluenceUrl(
            target_type="page", space_key="DEV", page_id="67890", page_title="My-Title"
        )

    def test_spaces_pages_without_title(self) -> None:
        result = parse_confluence_url("https://confluence.example.com/spaces/DEV/pages/67890")
        assert result == ParsedConfluenceUrl(
            target_type="page", space_key="DEV", page_id="67890", page_title=None
        )

    def test_unrecognized_url_raises(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized Confluence URL pattern"):
            parse_confluence_url("https://confluence.example.com/unknown/path")

    def test_viewpage_missing_page_id_raises(self) -> None:
        with pytest.raises(ValueError, match="missing pageId"):
            parse_confluence_url("https://confluence.example.com/pages/viewpage.action")
