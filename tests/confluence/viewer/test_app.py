"""Tests for confluence.viewer.app module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from atlassian_backup.confluence.viewer.app import create_app


@pytest.fixture()
def backup_dir(tmp_path: Path) -> Path:
    """Create a backup directory with test data."""
    manifest = {
        "backup_name": "test-backup",
        "backup_type": "page",
        "source_url": "https://example.com/spaces/TEST/pages/100/Root",
        "space_key": "TEST",
        "root_page_id": "100",
        "statistics": {
            "pages_backed_up": 2,
            "blog_posts_backed_up": 0,
            "attachments_downloaded": 1,
            "comments_backed_up": 1,
            "total_errors": 0,
        },
        "page_tree": [
            {
                "id": "100",
                "title": "Root Page",
                "children": [
                    {"id": "200", "title": "Child Page", "children": []},
                ],
            }
        ],
        "errors": [],
    }
    (tmp_path / "backup_manifest.json").write_text(json.dumps(manifest))

    # Root page
    page_dir = tmp_path / "pages" / "100"
    page_dir.mkdir(parents=True)
    page_data = {
        "id": "100",
        "title": "Root Page",
        "space_key": "TEST",
        "body_storage": "<p>Root content</p>",
        "version_number": 3,
        "created_by": "Author",
        "created_date": "2025-01-01T10:00:00.000+00:00",
        "last_updated_by": "Editor",
        "last_updated_date": "2025-06-01T10:00:00.000+00:00",
        "ancestors": [],
        "labels": ["docs"],
        "children_ids": ["200"],
    }
    (page_dir / "page.json").write_text(json.dumps(page_data))

    comments = [
        {
            "id": "c1",
            "body_storage": "<p>Nice page!</p>",
            "created_by": "Reviewer",
            "created_date": "2025-02-01T10:00:00.000+00:00",
        }
    ]
    (page_dir / "comments.json").write_text(json.dumps(comments))

    attachments = [
        {
            "id": "a1",
            "title": "diagram.png",
            "mediaType": "image/png",
            "fileSize": 2048,
            "downloadUrl": "/download/100/diagram.png",
        }
    ]
    (page_dir / "attachments.json").write_text(json.dumps(attachments))

    att_dir = page_dir / "attachments"
    att_dir.mkdir()
    (att_dir / "diagram.png").write_bytes(b"\x89PNG fake image data")

    return tmp_path


@pytest.fixture()
def client(backup_dir: Path) -> FlaskClient:
    """Create a Flask test client."""
    app = create_app(backup_dir)
    app.config["TESTING"] = True
    return app.test_client()


class TestHomeRoute:
    def test_home_status(self, client: FlaskClient) -> None:
        response = client.get("/")
        assert response.status_code == 200

    def test_home_contains_backup_name(self, client: FlaskClient) -> None:
        response = client.get("/")
        assert b"test-backup" in response.data

    def test_home_contains_stats(self, client: FlaskClient) -> None:
        response = client.get("/")
        html = response.data.decode()
        assert "Pages" in html
        assert "Attachments" in html

    def test_home_contains_page_tree(self, client: FlaskClient) -> None:
        response = client.get("/")
        html = response.data.decode()
        assert "Root Page" in html
        assert "Child Page" in html


class TestPageRoute:
    def test_page_status(self, client: FlaskClient) -> None:
        response = client.get("/page/100")
        assert response.status_code == 200

    def test_page_not_found(self, client: FlaskClient) -> None:
        response = client.get("/page/999")
        assert response.status_code == 404

    def test_page_contains_title(self, client: FlaskClient) -> None:
        response = client.get("/page/100")
        assert b"Root Page" in response.data

    def test_page_contains_body(self, client: FlaskClient) -> None:
        response = client.get("/page/100")
        assert b"Root content" in response.data

    def test_page_contains_metadata(self, client: FlaskClient) -> None:
        response = client.get("/page/100")
        html = response.data.decode()
        assert "Author" in html
        assert "Version 3" in html

    def test_page_contains_comments(self, client: FlaskClient) -> None:
        response = client.get("/page/100")
        html = response.data.decode()
        assert "Nice page!" in html
        assert "Reviewer" in html

    def test_page_contains_attachments(self, client: FlaskClient) -> None:
        response = client.get("/page/100")
        html = response.data.decode()
        assert "diagram.png" in html
        assert "2.0 KB" in html

    def test_page_sidebar_active(self, client: FlaskClient) -> None:
        response = client.get("/page/100")
        html = response.data.decode()
        assert 'class="active"' in html


class TestAttachmentRoute:
    def test_attachment_download(self, client: FlaskClient) -> None:
        response = client.get("/attachment/100/diagram.png")
        assert response.status_code == 200
        assert response.data.startswith(b"\x89PNG")

    def test_attachment_not_found(self, client: FlaskClient) -> None:
        response = client.get("/attachment/100/nonexistent.png")
        assert response.status_code == 404

    def test_attachment_wrong_page(self, client: FlaskClient) -> None:
        response = client.get("/attachment/999/diagram.png")
        assert response.status_code == 404
