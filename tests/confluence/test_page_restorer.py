"""Tests for confluence.page_restorer module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import responses

from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.confluence.models import RestoreManifest
from atlassian_backup.confluence.page_restorer import (
    restore_attachments,
    restore_comments,
    restore_labels,
    restore_page,
    restore_page_tree,
)
from atlassian_backup.confluence.viewer.backup_reader import BackupData
from atlassian_backup.shared.auth import BearerTokenAuth
from atlassian_backup.shared.http_client import create_write_session

BASE_URL = "https://eureka.example.com"


def make_client() -> ConfluenceClient:
    session = create_write_session(BearerTokenAuth("test-token"))
    return ConfluenceClient(session, BASE_URL)


def make_manifest() -> RestoreManifest:
    return RestoreManifest(
        backup_name="test-backup",
        target_space_key="DEV",
        target_base_url=BASE_URL,
    )


def create_backup(tmp_path: Path) -> BackupData:
    """Create a minimal backup structure for testing."""
    backup_dir = tmp_path / "test-backup"
    backup_dir.mkdir()

    # Create manifest
    manifest = {
        "backup_name": "test-backup",
        "backup_type": "page",
        "source_url": "https://example.com/display/OLD",
        "space_key": "OLD",
        "root_page_id": "100",
        "statistics": {"pages_backed_up": 2},
        "page_tree": [
            {
                "id": "100",
                "title": "Root Page",
                "children": [{"id": "101", "title": "Child Page", "children": []}],
            }
        ],
        "errors": [],
    }
    (backup_dir / "backup_manifest.json").write_text(json.dumps(manifest))

    # Create page data
    pages_dir = backup_dir / "pages"
    for page_id, title in [("100", "Root Page"), ("101", "Child Page")]:
        page_dir = pages_dir / page_id
        page_dir.mkdir(parents=True)
        page_data = {
            "id": page_id,
            "title": title,
            "space_key": "OLD",
            "body_storage": f"<p>{title} content</p>",
            "labels": ["label1"],
            "children_ids": [],
        }
        (page_dir / "page.json").write_text(json.dumps(page_data))

    # Create comments for page 100
    comments = [
        {
            "id": "c1",
            "body_storage": "<p>A comment</p>",
            "created_by": "John Doe",
            "created_date": "2025-01-15T10:00:00Z",
        }
    ]
    (pages_dir / "100" / "comments.json").write_text(json.dumps(comments))

    # Create attachments for page 100
    att_dir = pages_dir / "100" / "attachments"
    att_dir.mkdir()
    (att_dir / "test.pdf").write_bytes(b"PDF content")
    att_meta = [
        {
            "id": "a1",
            "title": "test.pdf",
            "mediaType": "application/pdf",
            "fileSize": 11,
        }
    ]
    (pages_dir / "100" / "attachments.json").write_text(json.dumps(att_meta))

    return BackupData.load(backup_dir)


class TestRestorePage:
    @responses.activate
    def test_restore_page(self) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content",
            json={"id": "999", "title": "Root Page"},
            status=200,
        )
        client = make_client()
        page_data: dict[str, Any] = {
            "id": "100",
            "title": "Root Page",
            "body_storage": "<p>Content</p>",
        }
        new_id = restore_page(client, page_data, "DEV", None)
        assert new_id == "999"

    @responses.activate
    def test_restore_page_with_parent(self) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content",
            json={"id": "1000", "title": "Child"},
            status=200,
        )
        client = make_client()
        page_data: dict[str, Any] = {
            "id": "101",
            "title": "Child",
            "body_storage": "<p>Child</p>",
        }
        new_id = restore_page(client, page_data, "DEV", "999")
        assert new_id == "1000"


class TestRestoreLabels:
    @responses.activate
    def test_restore_labels(self) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content/999/label",
            json=[],
            status=200,
        )
        client = make_client()
        manifest = make_manifest()
        count = restore_labels(client, "999", ["label1", "label2"], manifest)
        assert count == 2
        assert manifest.labels_restored == 2

    def test_restore_labels_empty(self) -> None:
        client = make_client()
        manifest = make_manifest()
        count = restore_labels(client, "999", [], manifest)
        assert count == 0

    @responses.activate
    def test_restore_labels_error(self) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content/999/label",
            json={"message": "error"},
            status=500,
        )
        client = make_client()
        manifest = make_manifest()
        count = restore_labels(client, "999", ["label1"], manifest)
        assert count == 0
        assert len(manifest.errors) == 1


class TestRestoreAttachments:
    @responses.activate
    def test_restore_attachments(self, tmp_path: Path) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content/999/child/attachment",
            json={"results": [{"id": "att-new"}]},
            status=200,
        )
        backup = create_backup(tmp_path)
        client = make_client()
        manifest = make_manifest()
        count = restore_attachments(client, "999", backup, "100", manifest)
        assert count == 1
        assert manifest.attachments_uploaded == 1

    def test_restore_attachments_no_meta(self, tmp_path: Path) -> None:
        backup = create_backup(tmp_path)
        client = make_client()
        manifest = make_manifest()
        # Page 101 has no attachments
        count = restore_attachments(client, "999", backup, "101", manifest)
        assert count == 0


class TestRestoreComments:
    @responses.activate
    def test_restore_comments(self, tmp_path: Path) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content",
            json={"id": "c-new", "type": "comment"},
            status=200,
        )
        backup = create_backup(tmp_path)
        client = make_client()
        manifest = make_manifest()
        count = restore_comments(client, "999", backup, "100", manifest)
        assert count == 1
        assert manifest.comments_restored == 1
        # Verify attribution prefix in body
        body = responses.calls[0].request.body
        assert body is not None
        assert b"John Doe" in body

    def test_restore_comments_none(self, tmp_path: Path) -> None:
        backup = create_backup(tmp_path)
        client = make_client()
        manifest = make_manifest()
        # Page 101 has no comments
        count = restore_comments(client, "999", backup, "101", manifest)
        assert count == 0


class TestRestorePageTree:
    @responses.activate
    def test_restore_tree(self, tmp_path: Path) -> None:
        # Two pages need creation: root (100) and child (101)
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content",
            json={"id": "900", "title": "Root Page"},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content/900/label",
            json=[],
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content/900/child/attachment",
            json={"results": [{"id": "att-new"}]},
            status=200,
        )
        # Comment for page 100
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content",
            json={"id": "c-new", "type": "comment"},
            status=200,
        )
        # Child page creation
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content",
            json={"id": "901", "title": "Child Page"},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content/901/label",
            json=[],
            status=200,
        )

        backup = create_backup(tmp_path)
        client = make_client()
        manifest = make_manifest()
        flush_calls: list[int] = []

        restore_page_tree(
            client,
            backup,
            backup.page_tree,
            "DEV",
            None,
            manifest,
            skip_comments=False,
            skip_attachments=False,
            flush_callback=lambda: flush_calls.append(1),
        )

        assert manifest.pages_restored == 2
        assert "100" in manifest.id_mapping
        assert "101" in manifest.id_mapping
        assert manifest.id_mapping["100"] == "900"
        assert len(flush_calls) == 2

    @responses.activate
    def test_resume_skips_restored(self, tmp_path: Path) -> None:
        # Only child page needs creation - root already in id_mapping
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content",
            json={"id": "901", "title": "Child Page"},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content/901/label",
            json=[],
            status=200,
        )

        backup = create_backup(tmp_path)
        client = make_client()
        manifest = make_manifest()
        manifest.id_mapping["100"] = "900"  # Already restored

        restore_page_tree(
            client,
            backup,
            backup.page_tree,
            "DEV",
            None,
            manifest,
            skip_comments=True,
            skip_attachments=True,
        )

        assert manifest.pages_restored == 1
        assert manifest.id_mapping["101"] == "901"
