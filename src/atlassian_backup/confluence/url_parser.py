"""Confluence URL pattern detection for Server/Data Center instances."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class ParsedConfluenceUrl:
    """Result of parsing a Confluence URL."""

    target_type: str  # "space" or "page"
    space_key: str | None = None
    page_id: str | None = None
    page_title: str | None = None


def parse_confluence_url(url: str) -> ParsedConfluenceUrl:
    """Parse a Confluence Server/DC URL to determine target type and identifiers.

    Supported patterns:
        /display/{SPACEKEY}                         -> space
        /spaces/{SPACEKEY}                          -> space
        /spaces/{SPACEKEY}/overview                 -> space
        /display/{SPACEKEY}/{PageTitle}             -> page (by title)
        /pages/viewpage.action?pageId={id}          -> page (by ID)
        /spaces/{SPACEKEY}/pages/{pageId}/{title}   -> page (by ID)

    Args:
        url: Full Confluence URL.

    Returns:
        ParsedConfluenceUrl with target type and identifiers.

    Raises:
        ValueError: If the URL pattern is not recognized.
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    query = parse_qs(parsed.query)

    # /pages/viewpage.action?pageId={id}
    if path.endswith("/pages/viewpage.action") or path.endswith("/viewpage.action"):
        page_ids = query.get("pageId", [])
        if page_ids:
            return ParsedConfluenceUrl(target_type="page", page_id=page_ids[0])
        raise ValueError(f"viewpage.action URL missing pageId parameter: {url}")

    # /spaces/{SPACEKEY}/pages/{pageId}/{title}
    match = re.match(r"/spaces/([^/]+)/pages/(\d+)(?:/(.*))?$", path)
    if match:
        return ParsedConfluenceUrl(
            target_type="page",
            space_key=match.group(1),
            page_id=match.group(2),
            page_title=match.group(3),
        )

    # /display/{SPACEKEY}/{PageTitle}
    match = re.match(r"/display/([^/]+)/(.+)$", path)
    if match:
        return ParsedConfluenceUrl(
            target_type="page",
            space_key=match.group(1),
            page_title=match.group(2),
        )

    # /display/{SPACEKEY} (no trailing content -> space)
    match = re.match(r"/display/([^/]+)$", path)
    if match:
        return ParsedConfluenceUrl(target_type="space", space_key=match.group(1))

    # /spaces/{SPACEKEY}/overview or /spaces/{SPACEKEY}
    match = re.match(r"/spaces/([^/]+)(?:/overview)?$", path)
    if match:
        return ParsedConfluenceUrl(target_type="space", space_key=match.group(1))

    raise ValueError(
        f"Unrecognized Confluence URL pattern: {url}\n"
        "Expected patterns:\n"
        "  /display/SPACEKEY\n"
        "  /display/SPACEKEY/PageTitle\n"
        "  /pages/viewpage.action?pageId=12345\n"
        "  /spaces/SPACEKEY/pages/12345/Title"
    )
