"""Export comments for Confluence pages."""

from __future__ import annotations

import logging
from typing import Any

from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.confluence.models import BackupManifest
from atlassian_backup.shared.backup_writer import BackupWriter

logger = logging.getLogger("atlassian_backup")


def export_comments(
    client: ConfluenceClient,
    writer: BackupWriter,
    page_id: str,
    content_type: str,
    manifest: BackupManifest,
) -> list[dict[str, Any]]:
    """Export all comments for a page.

    Args:
        client: Confluence API client.
        writer: Backup writer.
        page_id: Page ID.
        content_type: "pages" or "blog_posts" (for path prefix).
        manifest: Backup manifest for tracking.

    Returns:
        List of comment data dicts.
    """
    comments: list[dict[str, Any]] = []

    for comment_data in client.get_page_comments(page_id):
        comment_id = comment_data.get("id", "unknown")
        try:
            comment = {
                "id": comment_id,
                "body_storage": (comment_data.get("body", {}).get("storage", {}).get("value", "")),
                "created_by": (
                    comment_data.get("history", {}).get("createdBy", {}).get("displayName", "")
                ),
                "created_date": comment_data.get("history", {}).get("createdDate", ""),
                "raw_data": comment_data,
            }
            comments.append(comment)
            manifest.comments_backed_up += 1

        except Exception as e:
            logger.warning("Failed to process comment %s on page %s: %s", comment_id, page_id, e)
            manifest.add_error("comment", comment_id, str(e))

    if comments:
        writer.write_json(f"{content_type}/{page_id}/comments.json", comments)
        logger.debug("Exported %d comments for page %s", len(comments), page_id)

    return comments
