"""Tests for confluence.user_collector module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import responses

from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.confluence.models import BackupManifest
from atlassian_backup.confluence.user_collector import (
    _collect_keys_from_content,
    _collect_keys_from_metadata,
    collect_users,
)
from atlassian_backup.shared.auth import BearerTokenAuth
from atlassian_backup.shared.backup_writer import BackupWriter
from atlassian_backup.shared.http_client import create_session

BASE_URL = "https://eureka.example.com"


def make_client() -> ConfluenceClient:
    session = create_session(BearerTokenAuth("test-token"))
    return ConfluenceClient(session, BASE_URL)


def make_manifest() -> BackupManifest:
    return BackupManifest(
        backup_name="test-backup",
        backup_type="space",
        source_url=BASE_URL,
        space_key="TEST",
    )


def _setup_backup(tmp_path: Path) -> Path:
    """Create a backup directory with pages and blog posts for testing."""
    backup_dir = tmp_path / "test-backup"

    # Page with user mention in body and metadata
    page_dir = backup_dir / "pages" / "100"
    page_dir.mkdir(parents=True)
    (page_dir / "raw_response.json").write_text(
        json.dumps(
            {
                "history": {
                    "createdBy": {
                        "userKey": "key-alice",
                        "displayName": "Alice Smith",
                    }
                },
                "version": {
                    "by": {
                        "userKey": "key-bob",
                        "displayName": "Bob Jones",
                    }
                },
            }
        )
    )
    (page_dir / "page.json").write_text(
        json.dumps(
            {
                "id": "100",
                "title": "Test Page",
                "body_storage": (
                    '<p>Hello <ac:link><ri:user ri:userkey="key-charlie" /></ac:link></p>'
                ),
            }
        )
    )
    # Comments with user mention
    (page_dir / "comments.json").write_text(
        json.dumps(
            [
                {
                    "id": "c1",
                    "body_storage": (
                        '<p>CC <ac:link><ri:user ri:userkey="key-dave" /></ac:link></p>'
                    ),
                }
            ]
        )
    )

    # Blog post
    blog_dir = backup_dir / "blog_posts" / "b1"
    blog_dir.mkdir(parents=True)
    (blog_dir / "raw_response.json").write_text(
        json.dumps(
            {
                "history": {
                    "createdBy": {
                        "userKey": "key-alice",
                        "displayName": "Alice Smith",
                    }
                },
                "version": {"by": {}},
            }
        )
    )
    (blog_dir / "post.json").write_text(
        json.dumps(
            {
                "id": "b1",
                "title": "Blog",
                "body_storage": '<p>By <ac:link><ri:user ri:userkey="key-alice" /></ac:link></p>',
            }
        )
    )

    return backup_dir


class TestCollectKeysFromMetadata:
    def test_extracts_from_raw_response(self, tmp_path: Path) -> None:
        backup_dir = _setup_backup(tmp_path)
        mapping = _collect_keys_from_metadata(backup_dir)
        assert mapping["key-alice"] == "Alice Smith"
        assert mapping["key-bob"] == "Bob Jones"

    def test_empty_backup(self, tmp_path: Path) -> None:
        backup_dir = tmp_path / "empty"
        backup_dir.mkdir()
        mapping = _collect_keys_from_metadata(backup_dir)
        assert mapping == {}


class TestCollectKeysFromContent:
    def test_extracts_from_bodies_and_comments(self, tmp_path: Path) -> None:
        backup_dir = _setup_backup(tmp_path)
        keys = _collect_keys_from_content(backup_dir)
        assert "key-charlie" in keys
        assert "key-dave" in keys
        assert "key-alice" in keys  # from blog body

    def test_empty_backup(self, tmp_path: Path) -> None:
        backup_dir = tmp_path / "empty"
        backup_dir.mkdir()
        keys = _collect_keys_from_content(backup_dir)
        assert keys == set()


class TestCollectUsers:
    @responses.activate
    def test_resolves_unknown_keys_via_api(self, tmp_path: Path) -> None:
        backup_dir = _setup_backup(tmp_path)

        # Use callback to return correct user based on query param
        user_data = {
            "key-charlie": {"userKey": "key-charlie", "displayName": "Charlie Brown"},
            "key-dave": {"userKey": "key-dave", "displayName": "Dave Wilson"},
        }

        def user_callback(request: Any) -> tuple[int, dict[str, str], str]:
            key = request.params.get("key", "")
            if key in user_data:
                return (200, {}, json.dumps(user_data[key]))
            return (404, {}, json.dumps({"message": "not found"}))

        responses.add_callback(
            responses.GET,
            f"{BASE_URL}/rest/api/user",
            callback=user_callback,
        )

        client = make_client()
        writer = BackupWriter(backup_dir)
        manifest = make_manifest()

        collect_users(client, writer, manifest)

        # Verify users.json was written
        users_path = backup_dir / "users.json"
        assert users_path.exists()
        users = json.loads(users_path.read_text())
        assert users["key-alice"] == "Alice Smith"
        assert users["key-bob"] == "Bob Jones"
        assert users["key-charlie"] == "Charlie Brown"
        assert users["key-dave"] == "Dave Wilson"
        assert manifest.users_collected == 4

    @responses.activate
    def test_handles_api_failure_gracefully(self, tmp_path: Path) -> None:
        backup_dir = _setup_backup(tmp_path)

        # API returns 404 for unknown keys
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/user",
            json={"message": "not found"},
            status=404,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/user",
            json={"message": "not found"},
            status=404,
        )

        client = make_client()
        writer = BackupWriter(backup_dir)
        manifest = make_manifest()

        collect_users(client, writer, manifest)

        users_path = backup_dir / "users.json"
        users = json.loads(users_path.read_text())
        # Only metadata keys should be present
        assert "key-alice" in users
        assert "key-bob" in users
        assert "key-charlie" not in users
        assert "key-dave" not in users
        assert manifest.users_collected == 2

    @responses.activate
    def test_no_api_calls_when_all_keys_known(self, tmp_path: Path) -> None:
        """When all userkeys in content are already in metadata, no API calls needed."""
        backup_dir = tmp_path / "backup"
        page_dir = backup_dir / "pages" / "100"
        page_dir.mkdir(parents=True)
        (page_dir / "raw_response.json").write_text(
            json.dumps(
                {
                    "history": {"createdBy": {"userKey": "key-x", "displayName": "User X"}},
                    "version": {"by": {}},
                }
            )
        )
        (page_dir / "page.json").write_text(
            json.dumps(
                {
                    "id": "100",
                    "body_storage": '<ac:link><ri:user ri:userkey="key-x" /></ac:link>',
                }
            )
        )

        client = make_client()
        writer = BackupWriter(backup_dir)
        manifest = make_manifest()

        collect_users(client, writer, manifest)

        # No API calls should have been made
        assert len(responses.calls) == 0
        assert manifest.users_collected == 1
