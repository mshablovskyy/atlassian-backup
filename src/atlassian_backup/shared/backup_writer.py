"""Write backup data to folder or ZIP archive."""

from __future__ import annotations

import json
import logging
import shutil
import zipfile
from pathlib import Path
from typing import Any

logger = logging.getLogger("atlassian_backup")


class BackupWriter:
    """Writes backup files to a directory, with optional ZIP compression."""

    def __init__(self, backup_dir: Path) -> None:
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def write_json(self, relative_path: str, data: Any) -> Path:
        """Write a JSON file to the backup directory.

        Args:
            relative_path: Path relative to backup root (e.g., "pages/123/page.json").
            data: Data to serialize as JSON.

        Returns:
            Absolute path of the written file.
        """
        file_path = self.backup_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.debug("Wrote JSON: %s", relative_path)
        return file_path

    def write_binary(self, relative_path: str, content: bytes) -> Path:
        """Write binary content (e.g., attachment) to the backup directory.

        Args:
            relative_path: Path relative to backup root.
            content: Binary content to write.

        Returns:
            Absolute path of the written file.
        """
        file_path = self.backup_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        logger.debug("Wrote binary: %s (%d bytes)", relative_path, len(content))
        return file_path

    def create_zip(self, destination: Path | None = None) -> Path:
        """Compress the backup directory into a ZIP archive.

        Args:
            destination: Path for the ZIP file. If None, places it next to
                the backup directory (``backup_dir.with_suffix(".zip")``).

        Returns:
            Path to the created ZIP file.
        """
        zip_path = destination if destination else self.backup_dir.with_suffix(".zip")
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Creating ZIP archive: %s", zip_path.name)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(self.backup_dir.rglob("*")):
                if file_path.is_file():
                    arcname = file_path.relative_to(self.backup_dir)
                    zf.write(file_path, arcname)

        # Remove the uncompressed directory after zipping
        shutil.rmtree(self.backup_dir)
        logger.info("ZIP archive created: %s", zip_path.name)
        return zip_path
