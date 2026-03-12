"""Tests for confluence.models module."""

from __future__ import annotations

from atlassian_backup.confluence.models import BackupManifest, RestoreManifest


class TestBackupManifest:
    def test_defaults(self) -> None:
        m = BackupManifest(
            backup_name="test",
            backup_type="space",
            source_url="https://example.com",
        )
        assert m.pages_backed_up == 0
        assert m.errors == []

    def test_add_error(self) -> None:
        m = BackupManifest(
            backup_name="test",
            backup_type="page",
            source_url="https://example.com",
        )
        m.add_error("page", "123", "Not found")
        assert len(m.errors) == 1
        assert m.errors[0]["type"] == "page"

    def test_to_dict(self) -> None:
        m = BackupManifest(
            backup_name="test-backup",
            backup_type="space",
            source_url="https://example.com",
            space_key="DEV",
        )
        m.pages_backed_up = 5
        m.add_error("page", "1", "err")

        d = m.to_dict()
        assert d["backup_name"] == "test-backup"
        assert d["statistics"]["pages_backed_up"] == 5
        assert d["statistics"]["total_errors"] == 1
        assert len(d["errors"]) == 1


class TestRestoreManifest:
    def test_defaults(self) -> None:
        m = RestoreManifest(
            backup_name="test",
            target_space_key="DEV",
            target_base_url="https://example.com",
        )
        assert m.pages_restored == 0
        assert m.id_mapping == {}
        assert m.errors == []

    def test_add_error(self) -> None:
        m = RestoreManifest(
            backup_name="test",
            target_space_key="DEV",
            target_base_url="https://example.com",
        )
        m.add_error("page", "123", "Failed")
        assert len(m.errors) == 1
        assert m.errors[0]["type"] == "page"

    def test_to_dict(self) -> None:
        m = RestoreManifest(
            backup_name="test",
            target_space_key="DEV",
            target_base_url="https://example.com",
            parent_page_id="500",
        )
        m.pages_restored = 3
        m.id_mapping["100"] = "900"
        m.add_error("page", "1", "err")

        d = m.to_dict()
        assert d["backup_name"] == "test"
        assert d["target_space_key"] == "DEV"
        assert d["parent_page_id"] == "500"
        assert d["statistics"]["pages_restored"] == 3
        assert d["statistics"]["total_errors"] == 1
        assert d["id_mapping"]["100"] == "900"

    def test_from_dict_roundtrip(self) -> None:
        m = RestoreManifest(
            backup_name="test",
            target_space_key="DEV",
            target_base_url="https://example.com",
            parent_page_id="500",
        )
        m.pages_restored = 5
        m.attachments_uploaded = 10
        m.id_mapping["100"] = "900"
        m.id_mapping["101"] = "901"
        m.add_error("page", "102", "error")

        d = m.to_dict()
        m2 = RestoreManifest.from_dict(d)
        assert m2.backup_name == "test"
        assert m2.target_space_key == "DEV"
        assert m2.parent_page_id == "500"
        assert m2.pages_restored == 5
        assert m2.attachments_uploaded == 10
        assert m2.id_mapping == {"100": "900", "101": "901"}
        assert len(m2.errors) == 1
