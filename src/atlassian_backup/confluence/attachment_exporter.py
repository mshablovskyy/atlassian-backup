"""Export attachments for Confluence pages."""

from __future__ import annotations

import logging
import re
from typing import Any

from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.confluence.models import BackupManifest
from atlassian_backup.shared.backup_writer import BackupWriter

logger = logging.getLogger("atlassian_backup")


def sanitize_filename(name: str) -> str:
    """Sanitize a filename for safe filesystem storage.

    Args:
        name: Original filename.

    Returns:
        Sanitized filename safe for all platforms.
    """
    # Replace problematic characters with underscore
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # Collapse multiple underscores
    sanitized = re.sub(r"_+", "_", sanitized)
    # Limit length
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    return sanitized


def export_attachments(
    client: ConfluenceClient,
    writer: BackupWriter,
    page_id: str,
    content_type: str,
    manifest: BackupManifest,
) -> list[dict[str, Any]]:
    """Export all attachments for a page or blog post.

    Args:
        client: Confluence API client.
        writer: Backup writer for persisting files.
        page_id: Page or blog post ID.
        content_type: "pages" or "blog_posts" (for path prefix).
        manifest: Backup manifest for tracking stats/errors.

    Returns:
        List of attachment metadata dicts.
    """
    attachments_meta: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for att_data in client.get_page_attachments(page_id):
        att_id = att_data.get("id", "unknown")
        att_title = att_data.get("title", "unknown")

        try:
            # Save attachment metadata
            meta = {
                "id": att_id,
                "title": att_title,
                "mediaType": att_data.get("metadata", {}).get("mediaType", ""),
                "fileSize": att_data.get("extensions", {}).get("fileSize", 0),
                "downloadUrl": att_data.get("_links", {}).get("download", ""),
            }
            attachments_meta.append(meta)

            # Download the binary
            download_url = att_data.get("_links", {}).get("download", "")
            if download_url:
                response = client.download_attachment(download_url)
                safe_name = sanitize_filename(att_title)
                if safe_name in seen_names:
                    dot_pos = safe_name.rfind(".")
                    if dot_pos > 0:
                        base, ext = safe_name[:dot_pos], safe_name[dot_pos:]
                    else:
                        base, ext = safe_name, ""
                    counter = 1
                    while f"{base}_{counter}{ext}" in seen_names:
                        counter += 1
                    safe_name = f"{base}_{counter}{ext}"
                    logger.warning(
                        "Filename collision for '%s' on page %s, saved as '%s'",
                        att_title,
                        page_id,
                        safe_name,
                    )
                seen_names.add(safe_name)
                writer.write_binary(
                    f"{content_type}/{page_id}/attachments/{safe_name}",
                    response.content,
                )
                manifest.attachments_downloaded += 1
                logger.info("Downloaded attachment: %s (page %s)", att_title, page_id)
            else:
                logger.warning("No download URL for attachment %s on page %s", att_id, page_id)

        except Exception as e:
            logger.warning(
                "Failed to download attachment %s (%s) on page %s: %s",
                att_id,
                att_title,
                page_id,
                e,
            )
            manifest.add_error("attachment", att_id, str(e))

    # Write attachment metadata JSON
    if attachments_meta:
        writer.write_json(f"{content_type}/{page_id}/attachments.json", attachments_meta)

    return attachments_meta
