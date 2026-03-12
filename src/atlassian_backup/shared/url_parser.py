"""Base URL parsing utilities for Atlassian products."""

from __future__ import annotations

from urllib.parse import urlparse


def extract_base_url(url: str) -> str:
    """Extract the base URL (scheme + host) from a full URL.

    Args:
        url: Full URL like https://confluence.example.com/display/SPACE.

    Returns:
        Base URL like https://confluence.example.com
    """
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"
