"""Tests for confluence.restore_orchestrator module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import responses

from atlassian_backup.confluence.models import RestoreManifest
from atlassian_backup.confluence.restore_orchestrator import (
    _flush_manifest,
    _manifest_path_for,
    _print_dry_run_summary,
    run_restore,
)
from atlassian_backup.confluence.viewer.backup_reader import BackupData
from atlassian_backup.shared.config import ConfluenceConfig

BASE_URL = "https://eureka.example.com"


def create_test_backup(tmp_path: Path) -> Path:
    """Create a minimal backup for orchestrator testing."""
    backup_dir = tmp_path / "test-backup"
    backup_dir.mkdir()

    manifest = {
        "backup_name": "test-backup",
        "backup_type": "page",
        "source_url": "https://example.com/pages/viewpage.action?pageId=100",
        "space_key": "OLD",
        "root_page_id": "100",
        "statistics": {
            "pages_backed_up": 1,
            "blog_posts_backed_up": 0,
            "attachments_downloaded": 0,
            "comments_backed_up": 0,
        },
        "page_tree": [{"id": "100", "title": "Root Page", "children": []}],
        "errors": [],
    }
    (backup_dir / "backup_manifest.json").write_text(json.dumps(manifest))

    pages_dir = backup_dir / "pages" / "100"
    pages_dir.mkdir(parents=True)
    page_data = {
        "id": "100",
        "title": "Root Page",
        "space_key": "OLD",
        "body_storage": "<p>Hello</p>",
        "labels": [],
        "children_ids": [],
    }
    (pages_dir / "page.json").write_text(json.dumps(page_data))

    return backup_dir


class TestManifestPath:
    def test_manifest_path_format(self, tmp_path: Path) -> None:
        backup_dir = tmp_path / "my-backup"
        result = _manifest_path_for(backup_dir)
        assert result == tmp_path / "my-backup_restore_manifest.json"

    def test_manifest_path_is_sibling(self, tmp_path: Path) -> None:
        backup_dir = tmp_path / "output" / "backup-123"
        result = _manifest_path_for(backup_dir)
        assert result.parent == tmp_path / "output"


class TestFlushManifest:
    def test_flush_writes_json(self, tmp_path: Path) -> None:
        manifest = RestoreManifest(
            backup_name="test",
            target_space_key="DEV",
            target_base_url="https://example.com",
        )
        manifest.id_mapping["100"] = "900"
        path = tmp_path / "test_restore_manifest.json"
        _flush_manifest(manifest, path)

        assert path.exists()
        data = json.loads(path.read_text())
        assert data["id_mapping"]["100"] == "900"


class TestDryRun:
    def test_dry_run_prints_summary(self, tmp_path: Path, capsys: Any) -> None:
        backup_dir = create_test_backup(tmp_path)
        backup = BackupData.load(backup_dir)
        _print_dry_run_summary(backup)
        captured = capsys.readouterr()
        assert "Dry Run Summary" in captured.out
        assert "Root Page" in captured.out
        assert "test-backup" in captured.out


class TestRunRestore:
    @responses.activate
    def test_full_restore(self, tmp_path: Path) -> None:
        backup_dir = create_test_backup(tmp_path)

        # Mock verify connection
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/space",
            json={"results": [], "size": 0},
            status=200,
        )
        # Mock get_space
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/space/DEV",
            json={"key": "DEV", "name": "Development"},
            status=200,
        )
        # Mock create page
        responses.add(
            responses.POST,
            f"{BASE_URL}/rest/api/content",
            json={"id": "900", "title": "Root Page"},
            status=200,
        )

        config = ConfluenceConfig(base_url=BASE_URL, token="test-token")
        manifest_path, error_count = run_restore(
            config=config,
            backup_dir=backup_dir,
            space_key="DEV",
            skip_attachments=True,
            skip_comments=True,
        )

        assert manifest_path.exists()
        assert error_count == 0
        data = json.loads(manifest_path.read_text())
        assert data["statistics"]["pages_restored"] == 1
        assert data["id_mapping"]["100"] == "900"

    def test_dry_run_no_api_calls(self, tmp_path: Path) -> None:
        backup_dir = create_test_backup(tmp_path)
        config = ConfluenceConfig(base_url=BASE_URL, token="test-token")

        manifest_path, error_count = run_restore(
            config=config,
            backup_dir=backup_dir,
            space_key="DEV",
            dry_run=True,
        )

        # Should not create manifest file in dry-run
        assert not manifest_path.exists()
        assert error_count == 0

    @responses.activate
    def test_resume_restore(self, tmp_path: Path) -> None:
        backup_dir = create_test_backup(tmp_path)

        # Pre-create a restore manifest with page 100 already done
        existing_manifest = {
            "backup_name": "test-backup",
            "target_space_key": "DEV",
            "target_base_url": BASE_URL,
            "statistics": {
                "pages_restored": 1,
                "blog_posts_restored": 0,
                "attachments_uploaded": 0,
                "comments_restored": 0,
                "labels_restored": 0,
                "total_errors": 0,
            },
            "id_mapping": {"100": "900"},
            "errors": [],
        }
        manifest_path = backup_dir.parent / f"{backup_dir.name}_restore_manifest.json"
        manifest_path.write_text(json.dumps(existing_manifest))

        # Mock verify connection
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/space",
            json={"results": [], "size": 0},
            status=200,
        )
        # Mock get_space
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/space/DEV",
            json={"key": "DEV", "name": "Development"},
            status=200,
        )

        config = ConfluenceConfig(base_url=BASE_URL, token="test-token")
        result_path, error_count = run_restore(
            config=config,
            backup_dir=backup_dir,
            space_key="DEV",
            resume=True,
            skip_attachments=True,
            skip_comments=True,
        )

        assert error_count == 0
        data = json.loads(result_path.read_text())
        # Page 100 was already restored - should still be in mapping
        assert data["id_mapping"]["100"] == "900"
        # No new pages created (only had 1 page, already restored)
        assert data["statistics"]["pages_restored"] == 1
