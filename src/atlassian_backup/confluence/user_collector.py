"""Collect user-key-to-display-name mapping during Confluence backup."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.confluence.models import BackupManifest
from atlassian_backup.shared.backup_writer import BackupWriter

logger = logging.getLogger("atlassian_backup")

# Regex to find ri:userkey="..." in Confluence storage format
_USERKEY_PATTERN = re.compile(r'ri:userkey="([^"]+)"')


def _collect_keys_from_metadata(backup_dir: Path) -> dict[str, str]:
    """Scan raw_response.json files to extract userkeys with display names.

    Looks at ``history.createdBy`` and ``version.by`` in each raw response.

    Returns:
        Mapping of userkey -> displayName.
    """
    mapping: dict[str, str] = {}

    for subdir in ("pages", "blog_posts"):
        parent = backup_dir / subdir
        if not parent.exists():
            continue
        for item_dir in parent.iterdir():
            if not item_dir.is_dir():
                continue
            raw_path = item_dir / "raw_response.json"
            if not raw_path.exists():
                continue
            try:
                with open(raw_path) as f:
                    raw: dict[str, Any] = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            # history.createdBy
            created_by = raw.get("history", {}).get("createdBy", {})
            key = created_by.get("userKey")
            name = created_by.get("displayName")
            if key and name:
                mapping[key] = name

            # version.by
            version_by = raw.get("version", {}).get("by", {})
            key = version_by.get("userKey")
            name = version_by.get("displayName")
            if key and name:
                mapping[key] = name

    return mapping


def _scan_body_for_userkeys(body: str) -> set[str]:
    """Extract all userkeys from a Confluence storage-format body string."""
    return set(_USERKEY_PATTERN.findall(body))


def _collect_keys_from_content(backup_dir: Path) -> set[str]:
    """Scan page/blog bodies and comments for userkeys referenced in content.

    Returns:
        Set of all userkeys found in content bodies.
    """
    keys: set[str] = set()

    for subdir, data_file in (("pages", "page.json"), ("blog_posts", "post.json")):
        parent = backup_dir / subdir
        if not parent.exists():
            continue
        for item_dir in parent.iterdir():
            if not item_dir.is_dir():
                continue

            # Scan main body
            path = item_dir / data_file
            if path.exists():
                try:
                    with open(path) as f:
                        data: dict[str, Any] = json.load(f)
                    body = data.get("body_storage", "")
                    keys.update(_scan_body_for_userkeys(body))
                except (json.JSONDecodeError, OSError):
                    pass

            # Scan comments
            comments_path = item_dir / "comments.json"
            if comments_path.exists():
                try:
                    with open(comments_path) as f:
                        comments: list[dict[str, Any]] = json.load(f)
                    for comment in comments:
                        body = comment.get("body_storage", "")
                        keys.update(_scan_body_for_userkeys(body))
                except (json.JSONDecodeError, OSError):
                    pass

    return keys


def collect_users(
    client: ConfluenceClient,
    writer: BackupWriter,
    manifest: BackupManifest,
) -> None:
    """Collect a userkey-to-displayName mapping and write users.json.

    1. Extract known mappings from raw_response.json metadata.
    2. Scan all content bodies for userkey references.
    3. Query the API for any keys found in content but missing from metadata.
    4. Write users.json and update manifest.

    Args:
        client: Confluence API client (for resolving unknown keys).
        writer: Backup writer (for saving users.json).
        manifest: Backup manifest (updated with users_collected count).
    """
    backup_dir = writer.backup_dir

    # Step 1: Collect from metadata
    mapping = _collect_keys_from_metadata(backup_dir)
    logger.debug("Found %d user(s) from metadata", len(mapping))

    # Step 2: Scan content bodies
    content_keys = _collect_keys_from_content(backup_dir)
    logger.debug("Found %d unique userkey(s) in content bodies", len(content_keys))

    # Step 3: Resolve unknown keys via API
    unknown_keys = content_keys - set(mapping.keys())
    if unknown_keys:
        logger.info("Resolving %d unknown userkey(s) via API", len(unknown_keys))
        for key in unknown_keys:
            user_data = client.get_user_by_key(key)
            if user_data and user_data.get("displayName"):
                mapping[key] = user_data["displayName"]
            else:
                logger.debug("Could not resolve userkey: %s", key)

    # Step 4: Write users.json
    writer.write_json("users.json", mapping)
    manifest.users_collected = len(mapping)
    logger.info("Collected %d user mapping(s) -> users.json", len(mapping))
