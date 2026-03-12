"""Read backup data from disk for the viewer."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BackupData:
    """Provides access to backup data on disk.

    Loads the manifest eagerly at construction; page/comment/attachment
    data is loaded on demand.
    """

    backup_dir: Path
    backup_name: str = ""
    backup_type: str = ""
    source_url: str = ""
    space_key: str = ""
    root_page_id: str = ""
    statistics: dict[str, int] = field(default_factory=dict)
    page_tree: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def load(cls, backup_dir: Path) -> BackupData:
        """Load backup data from a directory.

        Args:
            backup_dir: Path to the backup directory containing backup_manifest.json.

        Returns:
            BackupData instance with manifest loaded.

        Raises:
            FileNotFoundError: If backup_manifest.json is missing.
            ValueError: If manifest JSON is invalid.
        """
        manifest_path = backup_dir / "backup_manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"backup_manifest.json not found in {backup_dir}")

        with open(manifest_path) as f:
            manifest = json.load(f)

        if not isinstance(manifest, dict):
            raise ValueError("Invalid backup manifest format")

        return cls(
            backup_dir=backup_dir,
            backup_name=manifest.get("backup_name", ""),
            backup_type=manifest.get("backup_type", ""),
            source_url=manifest.get("source_url", ""),
            space_key=manifest.get("space_key", ""),
            root_page_id=manifest.get("root_page_id", ""),
            statistics=manifest.get("statistics", {}),
            page_tree=manifest.get("page_tree", []),
            errors=manifest.get("errors", []),
        )

    def get_page(self, page_id: str) -> dict[str, Any] | None:
        """Load page data by ID.

        Tries pages/{id}/page.json first, then blog_posts/{id}/post.json.

        Args:
            page_id: The page ID to load.

        Returns:
            Page data dict or None if not found.
        """
        page_path = self.backup_dir / "pages" / page_id / "page.json"
        if page_path.exists():
            result: dict[str, Any] = self._read_json(page_path)
            return result

        blog_path = self.backup_dir / "blog_posts" / page_id / "post.json"
        if blog_path.exists():
            result = self._read_json(blog_path)
            return result

        return None

    def get_comments(self, page_id: str) -> list[dict[str, Any]]:
        """Load comments for a page.

        Args:
            page_id: The page ID.

        Returns:
            List of comment dicts, or empty list.
        """
        for prefix in ("pages", "blog_posts"):
            path = self.backup_dir / prefix / page_id / "comments.json"
            if path.exists():
                data = self._read_json(path)
                if isinstance(data, list):
                    return data
        return []

    def get_attachments_meta(self, page_id: str) -> list[dict[str, Any]]:
        """Load attachment metadata for a page.

        Args:
            page_id: The page ID.

        Returns:
            List of attachment metadata dicts, or empty list.
        """
        for prefix in ("pages", "blog_posts"):
            path = self.backup_dir / prefix / page_id / "attachments.json"
            if path.exists():
                data = self._read_json(path)
                if isinstance(data, list):
                    return data
        return []

    def get_attachment_path(self, page_id: str, filename: str) -> Path | None:
        """Resolve filesystem path to an attachment binary.

        Args:
            page_id: The page ID.
            filename: The sanitized filename.

        Returns:
            Path to the attachment file, or None if not found.
        """
        for prefix in ("pages", "blog_posts"):
            path = self.backup_dir / prefix / page_id / "attachments" / filename
            if path.exists():
                return path
        return None

    def build_title_index(self) -> dict[str, str]:
        """Build a mapping of page title -> page ID from the page tree.

        Returns:
            Dict mapping lowercase title to page ID.
        """
        index: dict[str, str] = {}
        self._walk_tree(self.page_tree, index)
        return index

    def get_all_page_ids(self) -> list[str]:
        """Get all page IDs from the page tree.

        Returns:
            List of all page IDs in the tree.
        """
        ids: list[str] = []
        self._collect_ids(self.page_tree, ids)
        return ids

    def _collect_ids(self, nodes: list[dict[str, Any]], ids: list[str]) -> None:
        for node in nodes:
            page_id = node.get("id", "")
            if page_id:
                ids.append(page_id)
            self._collect_ids(node.get("children", []), ids)

    def _walk_tree(self, nodes: list[dict[str, Any]], index: dict[str, str]) -> None:
        for node in nodes:
            title = node.get("title", "")
            page_id = node.get("id", "")
            if title and page_id:
                index[title.lower()] = page_id
            self._walk_tree(node.get("children", []), index)

    @staticmethod
    def _read_json(path: Path) -> Any:
        with open(path) as f:
            return json.load(f)
