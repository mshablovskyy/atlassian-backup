"""Recursive page tree export for Confluence backup."""

from __future__ import annotations

import logging
from typing import Any

from atlassian_backup.confluence.attachment_exporter import export_attachments
from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.confluence.comment_exporter import export_comments
from atlassian_backup.confluence.models import BackupManifest, Page
from atlassian_backup.shared.backup_writer import BackupWriter

logger = logging.getLogger("atlassian_backup")

MAX_DEPTH = 500


def _extract_page_model(data: dict[str, Any]) -> Page:
    """Extract a Page model from raw API response data."""
    history = data.get("history", {})
    version = data.get("version", {})
    space = data.get("space", {})
    labels_data = data.get("metadata", {}).get("labels", {}).get("results", [])

    return Page(
        id=data["id"],
        title=data.get("title", ""),
        space_key=space.get("key", ""),
        body_storage=data.get("body", {}).get("storage", {}).get("value", ""),
        version_number=version.get("number", 1),
        created_by=history.get("createdBy", {}).get("displayName", ""),
        created_date=history.get("createdDate", ""),
        last_updated_by=version.get("by", {}).get("displayName", ""),
        last_updated_date=version.get("when", ""),
        ancestors=[{"id": a["id"], "title": a.get("title", "")} for a in data.get("ancestors", [])],
        labels=[label.get("name", "") for label in labels_data],
        raw_data=data,
    )


def _page_to_dict(page: Page) -> dict[str, Any]:
    """Convert a Page model to a serializable dict."""
    return {
        "id": page.id,
        "title": page.title,
        "space_key": page.space_key,
        "body_storage": page.body_storage,
        "version_number": page.version_number,
        "created_by": page.created_by,
        "created_date": page.created_date,
        "last_updated_by": page.last_updated_by,
        "last_updated_date": page.last_updated_date,
        "ancestors": page.ancestors,
        "labels": page.labels,
        "children_ids": page.children_ids,
    }


def export_page(
    client: ConfluenceClient,
    writer: BackupWriter,
    page_id: str,
    manifest: BackupManifest,
    depth: int = 0,
) -> dict[str, Any] | None:
    """Export a single page with its comments, attachments, and recursively its children.

    Args:
        client: Confluence API client.
        writer: Backup writer.
        page_id: Page ID to export.
        manifest: Backup manifest for tracking.
        depth: Current recursion depth (for logging indentation).

    Returns:
        Page tree node dict (id, title, children) or None on failure.
    """
    if depth >= MAX_DEPTH:
        logger.warning(
            "Maximum page tree depth (%d) reached at page %s — skipping deeper children",
            MAX_DEPTH,
            page_id,
        )
        manifest.add_error("page", page_id, f"Max depth {MAX_DEPTH} exceeded")
        return None

    indent = "  " * depth
    try:
        # Fetch full page data
        raw_data = client.get_page(page_id)
    except Exception as e:
        logger.warning("%sSkipping page %s: %s", indent, page_id, e)
        manifest.add_error("page", page_id, str(e))
        return None

    page = _extract_page_model(raw_data)
    logger.info("%sExporting page: %s (%s)", indent, page.title, page.id)

    # Write structured page data
    writer.write_json(f"pages/{page.id}/page.json", _page_to_dict(page))

    # Write raw API response
    writer.write_json(f"pages/{page.id}/raw_response.json", raw_data)

    # Export comments
    export_comments(client, writer, page.id, "pages", manifest)

    # Export attachments
    export_attachments(client, writer, page.id, "pages", manifest)

    manifest.labels_backed_up += len(page.labels)
    manifest.pages_backed_up += 1

    # Recursively export child pages
    tree_node: dict[str, Any] = {
        "id": page.id,
        "title": page.title,
        "children": [],
    }

    for child_summary in client.get_child_pages(page.id):
        child_id = child_summary["id"]
        page.children_ids.append(child_id)
        child_node = export_page(client, writer, child_id, manifest, depth + 1)
        if child_node:
            tree_node["children"].append(child_node)

    # Re-write page.json with updated children_ids
    writer.write_json(f"pages/{page.id}/page.json", _page_to_dict(page))

    return tree_node
