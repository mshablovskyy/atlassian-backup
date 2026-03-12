"""Tests for shared.backup_writer module."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from atlassian_backup.shared.backup_writer import BackupWriter


class TestBackupWriter:
    def test_write_json(self, tmp_path: Path) -> None:
        writer = BackupWriter(tmp_path / "backup")
        path = writer.write_json("test/data.json", {"key": "value"})
        assert path.exists()
        data = json.loads(path.read_text())
        assert data == {"key": "value"}

    def test_write_binary(self, tmp_path: Path) -> None:
        writer = BackupWriter(tmp_path / "backup")
        content = b"binary content here"
        path = writer.write_binary("files/test.bin", content)
        assert path.exists()
        assert path.read_bytes() == content

    def test_write_json_creates_directories(self, tmp_path: Path) -> None:
        writer = BackupWriter(tmp_path / "backup")
        path = writer.write_json("deep/nested/dir/file.json", [1, 2, 3])
        assert path.exists()

    def test_create_zip(self, tmp_path: Path) -> None:
        backup_dir = tmp_path / "backup"
        writer = BackupWriter(backup_dir)
        writer.write_json("test.json", {"a": 1})
        writer.write_binary("test.bin", b"hello")

        zip_path = writer.create_zip()
        assert zip_path.exists()
        assert zip_path.suffix == ".zip"
        assert not backup_dir.exists()  # Original dir removed

        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "test.json" in names
            assert "test.bin" in names
