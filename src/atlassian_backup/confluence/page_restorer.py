"""Restore pages, labels, attachments, and comments to Confluence."""

from __future__ import annotations

import logging
from typing import Any

from atlassian_backup.confluence.attachment_exporter import sanitize_filename
from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.confluence.models import RestoreManifest
from atlassian_backup.confluence.user_resolver import resolve_user_references
from atlassian_backup.confluence.viewer.backup_reader import BackupData

logger = logging.getLogger("atlassian_backup")

MAX_DEPTH = 500


def restore_page(
    client: ConfluenceClient,
    page_data: dict[str, Any],
    space_key: str,
    parent_id: str | None,
    user_mapping: dict[str, str] | None = None,
) -> str:
    """Create a page in Confluence from backup data.

    Args:
        client: Confluence API client.
        page_data: Page data dict (from page.json).
        space_key: Target space key.
        parent_id: Parent page ID (new ID) or None for space root.
        user_mapping: Optional userkey-to-displayName mapping for resolution.

    Returns:
        New page ID.

    Raises:
        requests.HTTPError: On API failure.
    """
    title = page_data.get("title", "Untitled")
    body_storage = page_data.get("body_storage", "")
    if user_mapping:
        body_storage = resolve_user_references(body_storage, user_mapping)

    logger.debug(
        "Creating page: title=%s, space=%s, parent=%s, body_length=%d",
        title,
        space_key,
        parent_id or "(space root)",
        len(body_storage),
    )
    result = client.create_page(space_key, title, body_storage, parent_id)
    new_id: str = result["id"]
    logger.info("Created page: %s (old=%s, new=%s)", title, page_data.get("id"), new_id)
    return new_id


def restore_labels(
    client: ConfluenceClient,
    new_page_id: str,
    labels: list[str],
    manifest: RestoreManifest,
) -> int:
    """Add labels to a restored page.

    Args:
        client: Confluence API client.
        new_page_id: The new page ID in Confluence.
        labels: List of label names.
        manifest: Restore manifest for tracking.

    Returns:
        Number of labels added.
    """
    if not labels:
        return 0

    try:
        client.add_labels(new_page_id, labels)
        manifest.labels_restored += len(labels)
        logger.debug("Added %d labels to page %s", len(labels), new_page_id)
        return len(labels)
    except Exception as e:
        logger.warning("Failed to add labels to page %s: %s", new_page_id, e)
        manifest.add_error("labels", new_page_id, str(e))
        return 0


def restore_attachments(
    client: ConfluenceClient,
    new_page_id: str,
    backup: BackupData,
    old_page_id: str,
    manifest: RestoreManifest,
) -> int:
    """Upload attachments from backup to a restored page.

    Args:
        client: Confluence API client.
        new_page_id: The new page ID in Confluence.
        backup: Backup data reader.
        old_page_id: Original page ID (for locating backup files).
        manifest: Restore manifest for tracking.

    Returns:
        Number of attachments uploaded.
    """
    attachments_meta = backup.get_attachments_meta(old_page_id)
    if not attachments_meta:
        logger.debug("No attachments to restore for page %s", old_page_id)
        return 0

    logger.debug(
        "Restoring %d attachment(s) for page %s -> %s",
        len(attachments_meta),
        old_page_id,
        new_page_id,
    )
    uploaded = 0
    for att in attachments_meta:
        att_title = att.get("title", "unknown")
        att_id = att.get("id", "unknown")
        media_type = att.get("mediaType", "application/octet-stream")
        data = b""

        try:
            safe_name = sanitize_filename(att_title)
            att_path = backup.get_attachment_path(old_page_id, safe_name)
            if not att_path:
                logger.warning("Attachment file not found: %s (page %s)", safe_name, old_page_id)
                manifest.add_error("attachment", att_id, f"File not found: {safe_name}")
                continue

            data = att_path.read_bytes()
            logger.debug(
                "Uploading attachment: %s (%s, %d bytes) to page %s",
                att_title,
                media_type,
                len(data),
                new_page_id,
            )
            client.upload_attachment(new_page_id, att_title, data, media_type)
            manifest.attachments_uploaded += 1
            uploaded += 1
            logger.info("Uploaded attachment: %s (page %s)", att_title, new_page_id)

        except Exception as e:
            size_mb = len(data) / 1024 / 1024 if data else 0
            logger.warning(
                "Failed to upload attachment %s (%s, %.1f MB) to page %s: %s",
                att_id,
                att_title,
                size_mb,
                new_page_id,
                e,
            )
            manifest.add_error(
                "attachment",
                att_id,
                f"{e} [file: {att_title}, size: {size_mb:.1f} MB]",
            )

    return uploaded


def restore_comments(
    client: ConfluenceClient,
    new_page_id: str,
    backup: BackupData,
    old_page_id: str,
    manifest: RestoreManifest,
    user_mapping: dict[str, str] | None = None,
) -> int:
    """Recreate comments from backup on a restored page.

    Comments are created as the current authenticated user with a prefix
    noting the original author and date.

    Args:
        client: Confluence API client.
        new_page_id: The new page ID in Confluence.
        backup: Backup data reader.
        old_page_id: Original page ID (for locating backup data).
        manifest: Restore manifest for tracking.
        user_mapping: Optional userkey-to-displayName mapping for resolution.

    Returns:
        Number of comments restored.
    """
    comments = backup.get_comments(old_page_id)
    if not comments:
        logger.debug("No comments to restore for page %s", old_page_id)
        return 0

    logger.debug(
        "Restoring %d comment(s) for page %s -> %s",
        len(comments),
        old_page_id,
        new_page_id,
    )
    restored = 0
    for comment in comments:
        comment_id = comment.get("id", "unknown")
        original_body = comment.get("body_storage", "")
        original_author = comment.get("created_by", "Unknown")
        original_date = comment.get("created_date", "")

        try:
            if user_mapping:
                original_body = resolve_user_references(original_body, user_mapping)

            # Prefix with original author attribution
            attribution = f"<p><em>Originally by {original_author}"
            if original_date:
                attribution += f" on {original_date}"
            attribution += ":</em></p>"
            body = attribution + original_body

            logger.debug(
                "Restoring comment %s by %s on page %s",
                comment_id,
                original_author,
                new_page_id,
            )
            client.add_comment(new_page_id, body)
            manifest.comments_restored += 1
            restored += 1
            logger.info(
                "Restored comment %s (by %s) on page %s", comment_id, original_author, new_page_id
            )

        except Exception as e:
            logger.warning(
                "Failed to restore comment %s on page %s: %s",
                comment_id,
                new_page_id,
                e,
            )
            manifest.add_error("comment", comment_id, str(e))

    if restored:
        logger.debug("Restored %d comments on page %s", restored, new_page_id)

    return restored


def restore_page_tree(
    client: ConfluenceClient,
    backup: BackupData,
    tree_nodes: list[dict[str, Any]],
    space_key: str,
    parent_id: str | None,
    manifest: RestoreManifest,
    *,
    skip_attachments: bool = False,
    skip_comments: bool = False,
    flush_callback: Any | None = None,
    user_mapping: dict[str, str] | None = None,
    depth: int = 0,
) -> None:
    """Recursively restore a page tree.

    Args:
        client: Confluence API client.
        backup: Backup data reader.
        tree_nodes: List of page tree nodes (from backup manifest).
        space_key: Target space key.
        parent_id: Parent page ID (new) or None for root.
        manifest: Restore manifest for tracking progress.
        skip_attachments: Skip attachment upload.
        skip_comments: Skip comment creation.
        flush_callback: Called after each page to persist manifest.
        user_mapping: Optional userkey-to-displayName mapping for resolution.
        depth: Current recursion depth (for logging).
    """
    if depth >= MAX_DEPTH:
        logger.warning(
            "Maximum page tree depth (%d) reached — skipping deeper children",
            MAX_DEPTH,
        )
        return

    indent = "  " * depth
    for node in tree_nodes:
        old_id = node.get("id", "")
        title = node.get("title", "Untitled")
        children = node.get("children", [])

        # Resume support: skip already-restored pages
        if old_id in manifest.id_mapping:
            new_id = manifest.id_mapping[old_id]
            logger.info(
                "%sSkipping already restored: %s (old=%s, new=%s)", indent, title, old_id, new_id
            )
            # Still recurse into children using the existing new_id
            if children:
                restore_page_tree(
                    client,
                    backup,
                    children,
                    space_key,
                    new_id,
                    manifest,
                    skip_attachments=skip_attachments,
                    skip_comments=skip_comments,
                    flush_callback=flush_callback,
                    user_mapping=user_mapping,
                    depth=depth + 1,
                )
            continue

        # Load page data from backup
        page_data = backup.get_page(old_id)
        if not page_data:
            logger.warning("%sPage data not found in backup: %s (%s)", indent, title, old_id)
            manifest.add_error("page", old_id, "Page data not found in backup")
            continue

        labels = page_data.get("labels", [])
        att_count = len(backup.get_attachments_meta(old_id))
        comment_count = len(backup.get_comments(old_id))
        logger.debug(
            "%sRestoring page: %s (id=%s, labels=%d, attachments=%d, comments=%d, children=%d)",
            indent,
            title,
            old_id,
            len(labels),
            att_count,
            comment_count,
            len(children),
        )

        try:
            new_id = restore_page(client, page_data, space_key, parent_id, user_mapping)
            manifest.id_mapping[old_id] = new_id
            manifest.pages_restored += 1
        except Exception as e:
            logger.warning(
                "%sFailed to create page %s (%s): %s - skipping subtree",
                indent,
                title,
                old_id,
                e,
            )
            manifest.add_error("page", old_id, str(e))
            continue  # Skip entire subtree since children need this parent

        # Restore labels
        if labels:
            restore_labels(client, new_id, labels, manifest)

        # Restore attachments
        if not skip_attachments:
            restore_attachments(client, new_id, backup, old_id, manifest)

        # Restore comments
        if not skip_comments:
            restore_comments(client, new_id, backup, old_id, manifest, user_mapping)

        # Flush manifest for resume support
        if flush_callback:
            flush_callback()

        # Recurse into children
        if children:
            restore_page_tree(
                client,
                backup,
                children,
                space_key,
                new_id,
                manifest,
                skip_attachments=skip_attachments,
                skip_comments=skip_comments,
                flush_callback=flush_callback,
                user_mapping=user_mapping,
                depth=depth + 1,
            )
