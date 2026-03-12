"""Tests for confluence.blog_restorer module."""

from __future__ import annotations

import json
from pathlib import Path

import responses

from atlassian_backup.confluence.blog_restorer import restore_blog_posts
from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.confluence.models import RestoreManifest
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


def create_backup_with_blog(tmp_path: Path) -> BackupData:
    """Create a backup with blog posts for testing."""
    backup_dir = tmp_path / "test-backup"
    backup_dir.mkdir()

    manifest = {
        "backup_name": "test-backup",
        "backup_type": "space",
        "source_url": "https://example.com/display/OLD",
        "space_key": "OLD",
        "root_page_id": None,
        "statistics": {"pages_backed_up": 0, "blog_posts_backed_up": 1},
        "page_tree": [],
        "errors": [],
    }
    (backup_dir / "backup_manifest.json").write_text(json.dumps(manifest))

    # Create blog post
    blog_dir = backup_dir / "blog_posts" / "b1"
    blog_dir.mkdir(parents=True)
    post_data = {
        "id": "b1",
        "title": "My Blog Post",
        "space_key": "OLD",
        "body_storage": "<p>Blog content</p>",
        "created_by": "Author",
        "created_date": "2025-03-01T10:00:00Z",
    }
    (blog_dir / "post.json").write_text(json.dumps(post_data))

    # Create blog attachment
    att_dir = blog_dir / "attachments"
    att_dir.mkdir()
    (att_dir / "image.png").write_bytes(b"PNG data")
    att_meta = [{"id": "ba1", "title": "image.png", "mediaType": "image/png", "fileSize": 8}]
    (blog_dir / "attachments.json").write_text(json.dumps(att_meta))

    return BackupData.load(backup_dir)


class TestRestoreBlogPosts:
    @responses.activate
    def test_restore_blog_post(self, tmp_path: Path) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content",
            json={"id": "b-new", "title": "My Blog Post"},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content/b-new/child/attachment",
            json={"results": [{"id": "ba-new"}]},
            status=200,
        )
        backup = create_backup_with_blog(tmp_path)
        client = make_client()
        manifest = make_manifest()

        restore_blog_posts(client, backup, "DEV", manifest)

        assert manifest.blog_posts_restored == 1
        assert manifest.attachments_uploaded == 1
        assert "blog:b1" in manifest.id_mapping

    @responses.activate
    def test_restore_blog_skip_attachments(self, tmp_path: Path) -> None:
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content",
            json={"id": "b-new", "title": "My Blog Post"},
            status=200,
        )
        backup = create_backup_with_blog(tmp_path)
        client = make_client()
        manifest = make_manifest()

        restore_blog_posts(client, backup, "DEV", manifest, skip_attachments=True)

        assert manifest.blog_posts_restored == 1
        assert manifest.attachments_uploaded == 0

    @responses.activate
    def test_resume_skips_already_restored(self, tmp_path: Path) -> None:
        backup = create_backup_with_blog(tmp_path)
        client = make_client()
        manifest = make_manifest()
        manifest.id_mapping["blog:b1"] = "b-existing"

        restore_blog_posts(client, backup, "DEV", manifest)

        assert manifest.blog_posts_restored == 0
        assert len(responses.calls) == 0

    def test_no_blog_directory(self, tmp_path: Path) -> None:
        backup_dir = tmp_path / "empty-backup"
        backup_dir.mkdir()
        manifest_data = {
            "backup_name": "empty",
            "backup_type": "page",
            "source_url": "",
            "statistics": {},
            "page_tree": [],
            "errors": [],
        }
        (backup_dir / "backup_manifest.json").write_text(json.dumps(manifest_data))
        backup = BackupData.load(backup_dir)
        client = make_client()
        manifest = make_manifest()

        restore_blog_posts(client, backup, "DEV", manifest)
        assert manifest.blog_posts_restored == 0
