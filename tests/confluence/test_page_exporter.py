"""Tests for confluence.page_exporter module."""

from __future__ import annotations

import json
from pathlib import Path

import responses

from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.confluence.models import BackupManifest
from atlassian_backup.confluence.page_exporter import export_page
from atlassian_backup.shared.auth import BearerTokenAuth
from atlassian_backup.shared.backup_writer import BackupWriter
from atlassian_backup.shared.http_client import create_session

BASE_URL = "https://eureka.example.com"


def _make_page_response(page_id: str, title: str) -> dict:  # type: ignore[type-arg]
    return {
        "id": page_id,
        "title": title,
        "type": "page",
        "body": {"storage": {"value": f"<p>Content of {title}</p>"}},
        "version": {"number": 1, "by": {"displayName": "Author"}, "when": "2024-01-01"},
        "history": {
            "createdBy": {"displayName": "Creator"},
            "createdDate": "2024-01-01",
        },
        "space": {"key": "DEV"},
        "ancestors": [],
        "metadata": {"labels": {"results": [{"name": "test-label"}]}},
    }


class TestExportPage:
    @responses.activate
    def test_export_single_page(self, tmp_path: Path) -> None:
        # Mock page fetch
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/100",
            json=_make_page_response("100", "Test Page"),
            status=200,
        )
        # Mock child pages (empty)
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/100/child/page",
            json={"results": [], "size": 0},
            status=200,
        )
        # Mock comments (empty)
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/100/child/comment",
            json={"results": [], "size": 0},
            status=200,
        )
        # Mock attachments (empty)
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/100/child/attachment",
            json={"results": [], "size": 0},
            status=200,
        )

        session = create_session(BearerTokenAuth("test"))
        client = ConfluenceClient(session, BASE_URL)
        writer = BackupWriter(tmp_path / "backup")
        manifest = BackupManifest(backup_name="test", backup_type="page", source_url="http://test")

        tree = export_page(client, writer, "100", manifest)

        assert tree is not None
        assert tree["id"] == "100"
        assert tree["title"] == "Test Page"
        assert manifest.pages_backed_up == 1

        # Verify files written
        page_json = tmp_path / "backup" / "pages" / "100" / "page.json"
        assert page_json.exists()
        data = json.loads(page_json.read_text())
        assert data["title"] == "Test Page"
        assert data["labels"] == ["test-label"]

        raw_json = tmp_path / "backup" / "pages" / "100" / "raw_response.json"
        assert raw_json.exists()

    @responses.activate
    def test_export_page_with_children(self, tmp_path: Path) -> None:
        # Parent page
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/100",
            json=_make_page_response("100", "Parent"),
            status=200,
        )
        # Parent's children
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/100/child/page",
            json={"results": [{"id": "101", "title": "Child"}], "size": 1},
            status=200,
        )
        # Parent comments/attachments
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/100/child/comment",
            json={"results": [], "size": 0},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/100/child/attachment",
            json={"results": [], "size": 0},
            status=200,
        )
        # Child page
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/101",
            json=_make_page_response("101", "Child"),
            status=200,
        )
        # Child's children (none)
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/101/child/page",
            json={"results": [], "size": 0},
            status=200,
        )
        # Child comments/attachments
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/101/child/comment",
            json={"results": [], "size": 0},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/101/child/attachment",
            json={"results": [], "size": 0},
            status=200,
        )

        session = create_session(BearerTokenAuth("test"))
        client = ConfluenceClient(session, BASE_URL)
        writer = BackupWriter(tmp_path / "backup")
        manifest = BackupManifest(backup_name="test", backup_type="page", source_url="http://test")

        tree = export_page(client, writer, "100", manifest)

        assert tree is not None
        assert len(tree["children"]) == 1
        assert tree["children"][0]["id"] == "101"
        assert manifest.pages_backed_up == 2
