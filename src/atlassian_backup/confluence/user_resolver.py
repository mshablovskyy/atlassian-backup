"""Resolve user references in Confluence storage format content."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("atlassian_backup")

# Matches <ac:link><ri:user ri:userkey="..." /></ac:link> with optional inner content
_USER_LINK_PATTERN = re.compile(
    r"<ac:link>"
    r'\s*<ri:user\s+ri:userkey="([^"]*)"\s*/?\s*>'
    r"(.*?)"
    r"</ac:link>",
    re.DOTALL,
)


def load_user_mapping(backup_dir: Path) -> dict[str, str]:
    """Load the userkey-to-displayName mapping from users.json.

    Args:
        backup_dir: Path to the backup directory.

    Returns:
        Dict mapping userkey to displayName. Empty dict if file missing.
    """
    users_path = backup_dir / "users.json"
    if not users_path.exists():
        return {}
    try:
        with open(users_path) as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to read users.json from %s", backup_dir)
        return {}


def resolve_user_references(body: str, mapping: dict[str, str]) -> str:
    """Replace user mention links with @displayName plain text.

    Transforms ``<ac:link><ri:user ri:userkey="..." /></ac:link>`` into
    ``@displayName`` for known users or ``@[user:abcd1234...]`` for unknown.

    Args:
        body: Confluence storage format HTML body.
        mapping: Userkey-to-displayName mapping.

    Returns:
        Body with user references replaced.
    """
    if not body:
        return body

    def _replace(m: re.Match[str]) -> str:
        userkey = m.group(1)
        display_name = mapping.get(userkey)
        if display_name:
            return f"@{display_name}"
        short_key = userkey[:8] if len(userkey) > 8 else userkey
        return f"@[user:{short_key}...]"

    return _USER_LINK_PATTERN.sub(_replace, body)
