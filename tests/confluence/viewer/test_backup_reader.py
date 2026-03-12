"""Tests for confluence.viewer.backup_reader module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlassian_backup.confluence.viewer.backup_reader import BackupData


@pytest.fixture()
def backup_dir(tmp_path: Path) -> Path:
    """Create a minimal backup directory structure."""
    manifest = {
        "backup_name": "test-backup",
        "backup_type": "page",
        "source_url": "https://example.com/spaces/TEST/pages/123/Title",
        "space_key": "TEST",
        "root_page_id": "123",
        "statistics": {
            "pages_backed_up": 2,
            "blog_posts_backed_up": 0,
            "attachments_downloaded": 1,
            "comments_backed_up": 1,
            "total_errors": 0,
        },
        "page_tree": [
            {
                "id": "123",
                "title": "Root Page",
                "children": [
                    {"id": "456", "title": "Child Page", "children": []},
                ],
            }
        ],
        "errors": [],
    }
    (tmp_path / "backup_manifest.json").write_text(json.dumps(manifest))

    # Create page data
    pages_dir = tmp_path / "pages" / "123"
    pages_dir.mkdir(parents=True)
    page_data = {
        "id": "123",
        "title": "Root Page",
        "space_key": "TEST",
        "body_storage": "<p>Hello</p>",
        "version_number": 1,
        "created_by": "User",
        "created_date": "2025-01-01T00:00:00.000+00:00",
        "last_updated_by": "User",
        "last_updated_date": "2025-01-01T00:00:00.000+00:00",
        "ancestors": [],
        "labels": [],
        "children_ids": ["456"],
    }
    (pages_dir / "page.json").write_text(json.dumps(page_data))

    comments = [
        {
            "id": "789",
            "body_storage": "<p>A comment</p>",
            "created_by": "Commenter",
            "created_date": "2025-01-02T00:00:00.000+00:00",
        }
    ]
    (pages_dir / "comments.json").write_text(json.dumps(comments))

    attachments = [
        {
            "id": "att1",
            "title": "image.png",
            "mediaType": "image/png",
            "fileSize": 1024,
            "downloadUrl": "/download/123/image.png",
        }
    ]
    (pages_dir / "attachments.json").write_text(json.dumps(attachments))

    att_dir = pages_dir / "attachments"
    att_dir.mkdir()
    (att_dir / "image.png").write_bytes(b"\x89PNG")

    return tmp_path


class TestBackupDataLoad:
    def test_load_success(self, backup_dir: Path) -> None:
        data = BackupData.load(backup_dir)
        assert data.backup_name == "test-backup"
        assert data.backup_type == "page"
        assert data.space_key == "TEST"
        assert data.root_page_id == "123"
        assert data.statistics["pages_backed_up"] == 2

    def test_load_missing_manifest(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="backup_manifest.json"):
            BackupData.load(tmp_path)

    def test_load_invalid_manifest(self, tmp_path: Path) -> None:
        (tmp_path / "backup_manifest.json").write_text('"just a string"')
        with pytest.raises(ValueError, match="Invalid backup manifest"):
            BackupData.load(tmp_path)


class TestGetPage:
    def test_get_existing_page(self, backup_dir: Path) -> None:
        data = BackupData.load(backup_dir)
        page = data.get_page("123")
        assert page is not None
        assert page["title"] == "Root Page"

    def test_get_missing_page(self, backup_dir: Path) -> None:
        data = BackupData.load(backup_dir)
        assert data.get_page("999") is None

    def test_get_blog_post(self, backup_dir: Path) -> None:
        """Test fallback to blog_posts directory."""
        blog_dir = backup_dir / "blog_posts" / "blog1"
        blog_dir.mkdir(parents=True)
        post = {"id": "blog1", "title": "Blog Post"}
        (blog_dir / "post.json").write_text(json.dumps(post))

        data = BackupData.load(backup_dir)
        result = data.get_page("blog1")
        assert result is not None
        assert result["title"] == "Blog Post"


class TestGetComments:
    def test_get_comments(self, backup_dir: Path) -> None:
        data = BackupData.load(backup_dir)
        comments = data.get_comments("123")
        assert len(comments) == 1
        assert comments[0]["created_by"] == "Commenter"

    def test_get_comments_no_file(self, backup_dir: Path) -> None:
        data = BackupData.load(backup_dir)
        assert data.get_comments("456") == []


class TestGetAttachmentsMeta:
    def test_get_attachments(self, backup_dir: Path) -> None:
        data = BackupData.load(backup_dir)
        atts = data.get_attachments_meta("123")
        assert len(atts) == 1
        assert atts[0]["title"] == "image.png"

    def test_get_attachments_no_file(self, backup_dir: Path) -> None:
        data = BackupData.load(backup_dir)
        assert data.get_attachments_meta("456") == []


class TestGetAttachmentPath:
    def test_existing_attachment(self, backup_dir: Path) -> None:
        data = BackupData.load(backup_dir)
        path = data.get_attachment_path("123", "image.png")
        assert path is not None
        assert path.exists()

    def test_missing_attachment(self, backup_dir: Path) -> None:
        data = BackupData.load(backup_dir)
        assert data.get_attachment_path("123", "nope.png") is None


class TestBuildTitleIndex:
    def test_builds_index(self, backup_dir: Path) -> None:
        data = BackupData.load(backup_dir)
        index = data.build_title_index()
        assert index["root page"] == "123"
        assert index["child page"] == "456"


class TestGetAllPageIds:
    def test_gets_all_ids(self, backup_dir: Path) -> None:
        data = BackupData.load(backup_dir)
        ids = data.get_all_page_ids()
        assert set(ids) == {"123", "456"}
