"""Export Confluence space metadata."""

from __future__ import annotations

import logging
from typing import Any

from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.shared.backup_writer import BackupWriter

logger = logging.getLogger("atlassian_backup")


def export_space_metadata(
    client: ConfluenceClient,
    writer: BackupWriter,
    space_key: str,
) -> dict[str, Any]:
    """Export space metadata to the backup.

    Args:
        client: Confluence API client.
        writer: Backup writer.
        space_key: Space key.

    Returns:
        Space metadata dict.

    Raises:
        requests.HTTPError: If space cannot be fetched.
    """
    logger.info("Exporting space metadata: %s", space_key)
    space_data = client.get_space(space_key)

    metadata: dict[str, Any] = {
        "key": space_data.get("key", space_key),
        "name": space_data.get("name", ""),
        "description": (space_data.get("description", {}).get("plain", {}).get("value", "")),
        "homepage_id": space_data.get("homepage", {}).get("id"),
        "raw_data": space_data,
    }

    writer.write_json("space/space_metadata.json", metadata)
    logger.info("Space metadata exported: %s (%s)", metadata["name"], space_key)

    return metadata
