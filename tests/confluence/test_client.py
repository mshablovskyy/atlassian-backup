"""Tests for confluence.client module."""

from __future__ import annotations

import responses

from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.shared.auth import BearerTokenAuth
from atlassian_backup.shared.http_client import create_session

BASE_URL = "https://eureka.example.com"


def make_client() -> ConfluenceClient:
    session = create_session(BearerTokenAuth("test-token"))
    return ConfluenceClient(session, BASE_URL)


class TestConfluenceClient:
    @responses.activate
    def test_verify_connection(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/space",
            json={"results": [], "size": 0},
            status=200,
        )
        client = make_client()
        assert client.verify_connection() is True

    @responses.activate
    def test_verify_connection_401(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/space",
            json={"message": "Unauthorized"},
            status=401,
        )
        client = make_client()
        import pytest
        import requests

        with pytest.raises(requests.HTTPError, match="Authentication failed"):
            client.verify_connection()

    @responses.activate
    def test_get_space(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/space/DEV",
            json={"key": "DEV", "name": "Development"},
            status=200,
        )
        client = make_client()
        space = client.get_space("DEV")
        assert space["key"] == "DEV"

    @responses.activate
    def test_get_page(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/12345",
            json={"id": "12345", "title": "Test Page"},
            status=200,
        )
        client = make_client()
        page = client.get_page("12345")
        assert page["id"] == "12345"
        assert page["title"] == "Test Page"

    @responses.activate
    def test_get_page_by_title(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content",
            json={"results": [{"id": "111", "title": "My Page"}]},
            status=200,
        )
        client = make_client()
        page = client.get_page_by_title("DEV", "My Page")
        assert page is not None
        assert page["id"] == "111"

    @responses.activate
    def test_get_page_by_title_not_found(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content",
            json={"results": []},
            status=200,
        )
        client = make_client()
        page = client.get_page_by_title("DEV", "Nonexistent")
        assert page is None

    @responses.activate
    def test_get_child_pages(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/100/child/page",
            json={"results": [{"id": "101"}, {"id": "102"}], "size": 2},
            status=200,
        )
        client = make_client()
        children = list(client.get_child_pages("100"))
        assert len(children) == 2

    @responses.activate
    def test_get_page_comments(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/100/child/comment",
            json={"results": [{"id": "c1", "body": {"storage": {"value": "Hello"}}}], "size": 1},
            status=200,
        )
        client = make_client()
        comments = list(client.get_page_comments("100"))
        assert len(comments) == 1

    @responses.activate
    def test_get_page_attachments(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/100/child/attachment",
            json={
                "results": [
                    {"id": "a1", "title": "file.pdf", "_links": {"download": "/dl/file.pdf"}}
                ],
                "size": 1,
            },
            status=200,
        )
        client = make_client()
        attachments = list(client.get_page_attachments("100"))
        assert len(attachments) == 1
        assert attachments[0]["title"] == "file.pdf"

    @responses.activate
    def test_download_attachment(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/download/file.pdf",
            body=b"PDF content",
            status=200,
        )
        client = make_client()
        resp = client.download_attachment("/download/file.pdf")
        assert resp.content == b"PDF content"

    @responses.activate
    def test_get_space_blog_posts(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content",
            json={"results": [{"id": "b1", "title": "Blog Post"}], "size": 1},
            status=200,
        )
        client = make_client()
        posts = list(client.get_space_blog_posts("DEV"))
        assert len(posts) == 1
