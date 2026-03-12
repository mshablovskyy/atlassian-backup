"""Tests for Confluence client write methods."""

from __future__ import annotations

import responses

from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.shared.auth import BearerTokenAuth
from atlassian_backup.shared.http_client import create_write_session

BASE_URL = "https://eureka.example.com"


def make_client() -> ConfluenceClient:
    session = create_write_session(BearerTokenAuth("test-token"))
    return ConfluenceClient(session, BASE_URL)


class TestCreatePage:
    @responses.activate
    def test_create_page_basic(self) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content",
            json={"id": "999", "title": "New Page"},
            status=200,
        )
        client = make_client()
        result = client.create_page("DEV", "New Page", "<p>Content</p>")
        assert result["id"] == "999"

    @responses.activate
    def test_create_page_with_parent(self) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content",
            json={"id": "1000", "title": "Child Page"},
            status=200,
        )
        client = make_client()
        result = client.create_page("DEV", "Child Page", "<p>Child</p>", parent_id="500")
        assert result["id"] == "1000"
        # Verify request body included ancestors
        body = responses.calls[0].request.body
        assert body is not None
        assert b"500" in body


class TestCreateBlogPost:
    @responses.activate
    def test_create_blog_post(self) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content",
            json={"id": "2000", "title": "Blog Post"},
            status=200,
        )
        client = make_client()
        result = client.create_blog_post("DEV", "Blog Post", "<p>Blog</p>")
        assert result["id"] == "2000"


class TestAddLabels:
    @responses.activate
    def test_add_labels(self) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content/100/label",
            json=[],
            status=200,
        )
        client = make_client()
        client.add_labels("100", ["label1", "label2"])
        body = responses.calls[0].request.body
        assert body is not None
        assert b"label1" in body
        assert b"label2" in body

    @responses.activate
    def test_add_labels_empty(self) -> None:
        client = make_client()
        # Should not make any API call
        client.add_labels("100", [])
        assert len(responses.calls) == 0


class TestUploadAttachment:
    @responses.activate
    def test_upload_attachment(self) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content/100/child/attachment",
            json={"results": [{"id": "att1"}]},
            status=200,
        )
        client = make_client()
        result = client.upload_attachment("100", "file.pdf", b"binary data", "application/pdf")
        assert "results" in result
        # Verify X-Atlassian-Token header
        assert responses.calls[0].request.headers["X-Atlassian-Token"] == "nocheck"

    @responses.activate
    def test_upload_attachment_fallback_to_update(self) -> None:
        """When attachment already exists, fall back to updating it."""
        # First POST returns 400 "same file name"
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content/100/child/attachment",
            json={
                "statusCode": 400,
                "message": (
                    "Cannot add a new attachment with same file name"
                    " as an existing attachment: file.pdf"
                ),
            },
            status=400,
        )
        # GET to find existing attachment ID
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/100/child/attachment",
            json={"results": [{"id": "att-existing"}]},
            status=200,
        )
        # POST to update existing attachment data
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content/100/child/attachment/att-existing/data",
            json={"id": "att-existing", "title": "file.pdf"},
            status=200,
        )
        client = make_client()
        result = client.upload_attachment("100", "file.pdf", b"binary data", "application/pdf")
        assert result["id"] == "att-existing"
        assert len(responses.calls) == 3


class TestAddComment:
    @responses.activate
    def test_add_comment(self) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content",
            json={"id": "c1", "type": "comment"},
            status=200,
        )
        client = make_client()
        result = client.add_comment("100", "<p>A comment</p>")
        assert result["id"] == "c1"
        body = responses.calls[0].request.body
        assert body is not None
        assert b"comment" in body
