"""Restore blog posts to Confluence."""

from __future__ import annotations

import json
import logging
from typing import Any

from atlassian_backup.confluence.attachment_exporter import sanitize_filename
from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.confluence.models import RestoreManifest
from atlassian_backup.confluence.user_resolver import resolve_user_references
from atlassian_backup.confluence.viewer.backup_reader import BackupData

logger = logging.getLogger("atlassian_backup")


def restore_blog_posts(
    client: ConfluenceClient,
    backup: BackupData,
    space_key: str,
    manifest: RestoreManifest,
    *,
    skip_attachments: bool = False,
    user_mapping: dict[str, str] | None = None,
) -> None:
    """Restore all blog posts from backup to a space.

    Args:
        client: Confluence API client.
        backup: Backup data reader.
        space_key: Target space key.
        manifest: Restore manifest for tracking.
        skip_attachments: Skip attachment upload.
        user_mapping: Optional userkey-to-displayName mapping for resolution.
    """
    blog_dir = backup.backup_dir / "blog_posts"
    if not blog_dir.exists():
        logger.info("No blog posts directory found in backup")
        return

    logger.info("Restoring blog posts to space: %s", space_key)

    for post_dir in sorted(blog_dir.iterdir()):
        if not post_dir.is_dir():
            continue

        post_path = post_dir / "post.json"
        if not post_path.exists():
            continue

        old_id = post_dir.name
        # Skip already-restored blog posts (resume support)
        blog_key = f"blog:{old_id}"
        if blog_key in manifest.id_mapping:
            logger.info("Skipping already restored blog post: %s", old_id)
            continue

        try:
            with open(post_path) as f:
                post_data: dict[str, Any] = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read blog post %s: %s", old_id, e)
            manifest.add_error("blog_post", old_id, str(e))
            continue

        title = post_data.get("title", "Untitled")
        body_storage = post_data.get("body_storage", "")
        if user_mapping:
            body_storage = resolve_user_references(body_storage, user_mapping)

        try:
            result = client.create_blog_post(space_key, title, body_storage)
            new_id: str = result["id"]
            manifest.id_mapping[blog_key] = new_id
            manifest.blog_posts_restored += 1
            logger.info("Created blog post: %s (old=%s, new=%s)", title, old_id, new_id)
        except Exception as e:
            logger.warning("Failed to create blog post %s (%s): %s", old_id, title, e)
            manifest.add_error("blog_post", old_id, str(e))
            continue

        # Restore attachments
        if not skip_attachments:
            _restore_blog_attachments(client, backup, new_id, old_id, manifest)


def _restore_blog_attachments(
    client: ConfluenceClient,
    backup: BackupData,
    new_post_id: str,
    old_post_id: str,
    manifest: RestoreManifest,
) -> None:
    """Upload attachments for a restored blog post.

    Args:
        client: Confluence API client.
        backup: Backup data reader.
        new_post_id: New blog post ID.
        old_post_id: Original blog post ID.
        manifest: Restore manifest for tracking.
    """
    att_meta_path = backup.backup_dir / "blog_posts" / old_post_id / "attachments.json"
    if not att_meta_path.exists():
        return

    try:
        with open(att_meta_path) as f:
            attachments: list[dict[str, Any]] = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    for att in attachments:
        att_title = att.get("title", "unknown")
        att_id = att.get("id", "unknown")
        media_type = att.get("mediaType", "application/octet-stream")
        data = b""

        try:
            safe_name = sanitize_filename(att_title)
            att_path = backup.backup_dir / "blog_posts" / old_post_id / "attachments" / safe_name
            if not att_path.exists():
                manifest.add_error("attachment", att_id, f"File not found: {safe_name}")
                continue

            data = att_path.read_bytes()
            client.upload_attachment(new_post_id, att_title, data, media_type)
            manifest.attachments_uploaded += 1
            logger.info("Uploaded blog attachment: %s (post %s)", att_title, new_post_id)

        except Exception as e:
            size_mb = len(data) / 1024 / 1024 if data else 0
            logger.warning(
                "Failed to upload blog attachment %s (%s, %.1f MB) to post %s: %s",
                att_id,
                att_title,
                size_mb,
                new_post_id,
                e,
            )
            manifest.add_error(
                "attachment",
                att_id,
                f"{e} [file: {att_title}, size: {size_mb:.1f} MB]",
            )
