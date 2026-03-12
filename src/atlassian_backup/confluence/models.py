"""Domain models for Confluence backup data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Attachment:
    """Confluence attachment metadata."""

    id: str
    title: str
    media_type: str
    file_size: int
    download_url: str
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Comment:
    """Confluence page comment."""

    id: str
    body_storage: str
    created_by: str
    created_date: str
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Page:
    """Confluence page with metadata."""

    id: str
    title: str
    space_key: str
    body_storage: str
    version_number: int
    created_by: str
    created_date: str
    last_updated_by: str
    last_updated_date: str
    ancestors: list[dict[str, Any]] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    children_ids: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class BlogPost:
    """Confluence blog post."""

    id: str
    title: str
    space_key: str
    body_storage: str
    created_by: str
    created_date: str
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class SpaceMetadata:
    """Confluence space metadata."""

    key: str
    name: str
    description: str
    homepage_id: str | None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class BackupManifest:
    """Backup run metadata and statistics."""

    backup_name: str
    backup_type: str  # "space" or "page"
    source_url: str
    space_key: str | None = None
    root_page_id: str | None = None
    pages_backed_up: int = 0
    blog_posts_backed_up: int = 0
    attachments_downloaded: int = 0
    comments_backed_up: int = 0
    labels_backed_up: int = 0
    users_collected: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    page_tree: list[dict[str, Any]] = field(default_factory=list)

    def add_error(self, item_type: str, item_id: str, error: str) -> None:
        self.errors.append({"type": item_type, "id": item_id, "error": error})

    def to_dict(self) -> dict[str, Any]:
        return {
            "backup_name": self.backup_name,
            "backup_type": self.backup_type,
            "source_url": self.source_url,
            "space_key": self.space_key,
            "root_page_id": self.root_page_id,
            "statistics": {
                "pages_backed_up": self.pages_backed_up,
                "blog_posts_backed_up": self.blog_posts_backed_up,
                "attachments_downloaded": self.attachments_downloaded,
                "comments_backed_up": self.comments_backed_up,
                "labels_backed_up": self.labels_backed_up,
                "users_collected": self.users_collected,
                "total_errors": len(self.errors),
            },
            "page_tree": self.page_tree,
            "errors": self.errors,
        }


@dataclass
class RestoreManifest:
    """Restore run metadata, progress tracking, and ID mapping."""

    backup_name: str
    target_space_key: str
    target_base_url: str
    parent_page_id: str | None = None
    pages_restored: int = 0
    blog_posts_restored: int = 0
    attachments_uploaded: int = 0
    comments_restored: int = 0
    labels_restored: int = 0
    users_resolved: int = 0
    id_mapping: dict[str, str] = field(default_factory=dict)
    errors: list[dict[str, str]] = field(default_factory=list)

    def add_error(self, item_type: str, item_id: str, error: str) -> None:
        self.errors.append({"type": item_type, "id": item_id, "error": error})

    def to_dict(self) -> dict[str, Any]:
        return {
            "backup_name": self.backup_name,
            "target_space_key": self.target_space_key,
            "target_base_url": self.target_base_url,
            "parent_page_id": self.parent_page_id,
            "statistics": {
                "pages_restored": self.pages_restored,
                "blog_posts_restored": self.blog_posts_restored,
                "attachments_uploaded": self.attachments_uploaded,
                "comments_restored": self.comments_restored,
                "labels_restored": self.labels_restored,
                "users_resolved": self.users_resolved,
                "total_errors": len(self.errors),
            },
            "id_mapping": self.id_mapping,
            "errors": self.errors,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RestoreManifest:
        """Load a RestoreManifest from a dict (for resume support).

        Args:
            data: Dict previously created by to_dict().

        Returns:
            RestoreManifest instance.
        """
        stats = data.get("statistics", {})
        return cls(
            backup_name=data.get("backup_name", ""),
            target_space_key=data.get("target_space_key", ""),
            target_base_url=data.get("target_base_url", ""),
            parent_page_id=data.get("parent_page_id"),
            pages_restored=stats.get("pages_restored", 0),
            blog_posts_restored=stats.get("blog_posts_restored", 0),
            attachments_uploaded=stats.get("attachments_uploaded", 0),
            comments_restored=stats.get("comments_restored", 0),
            labels_restored=stats.get("labels_restored", 0),
            users_resolved=stats.get("users_resolved", 0),
            id_mapping=data.get("id_mapping", {}),
            errors=data.get("errors", []),
        )
