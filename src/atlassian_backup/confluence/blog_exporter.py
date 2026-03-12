"""Export blog posts for a Confluence space."""

from __future__ import annotations

import logging
from typing import Any

from atlassian_backup.confluence.attachment_exporter import export_attachments
from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.confluence.models import BackupManifest
from atlassian_backup.shared.backup_writer import BackupWriter

logger = logging.getLogger("atlassian_backup")


def export_blog_posts(
    client: ConfluenceClient,
    writer: BackupWriter,
    space_key: str,
    manifest: BackupManifest,
) -> None:
    """Export all blog posts in a space.

    Args:
        client: Confluence API client.
        writer: Backup writer.
        space_key: Space key to export blog posts from.
        manifest: Backup manifest for tracking.
    """
    logger.info("Exporting blog posts for space: %s", space_key)

    for blog_data in client.get_space_blog_posts(space_key):
        post_id = blog_data.get("id", "unknown")
        post_title = blog_data.get("title", "Untitled")

        try:
            history = blog_data.get("history", {})

            post_dict: dict[str, Any] = {
                "id": post_id,
                "title": post_title,
                "space_key": space_key,
                "body_storage": (blog_data.get("body", {}).get("storage", {}).get("value", "")),
                "created_by": history.get("createdBy", {}).get("displayName", ""),
                "created_date": history.get("createdDate", ""),
            }

            # Write structured post data
            writer.write_json(f"blog_posts/{post_id}/post.json", post_dict)

            # Write raw API response
            writer.write_json(f"blog_posts/{post_id}/raw_response.json", blog_data)

            # Export attachments
            export_attachments(client, writer, post_id, "blog_posts", manifest)

            manifest.blog_posts_backed_up += 1
            logger.info("Exported blog post: %s (%s)", post_title, post_id)

        except Exception as e:
            logger.warning("Failed to export blog post %s (%s): %s", post_id, post_title, e)
            manifest.add_error("blog_post", post_id, str(e))
