"""Generic offset-based pagination for Atlassian REST APIs."""

from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any

import requests

from atlassian_backup.shared.http_client import api_get

logger = logging.getLogger("atlassian_backup")


def paginated_get(
    session: requests.Session,
    url: str,
    params: dict[str, Any] | None = None,
    results_key: str = "results",
    limit: int = 25,
) -> Generator[dict[str, Any], None, None]:
    """Yield items from a paginated Confluence REST API endpoint.

    Uses offset-based pagination (start + limit parameters).
    Yields individual items from the results array.

    Args:
        session: Configured HTTP session.
        url: API endpoint URL.
        params: Additional query parameters.
        results_key: Key in response JSON containing the results array.
        limit: Number of items per page.

    Yields:
        Individual result dictionaries.
    """
    params = dict(params or {})
    params["limit"] = limit
    start = 0

    while True:
        params["start"] = start
        response = api_get(session, url, params=params)

        if response.status_code != 200:
            logger.error(
                "Pagination request failed: %s %s (status %d)",
                url,
                params,
                response.status_code,
            )
            raise RuntimeError(f"Pagination request failed: {url} (status {response.status_code})")

        data = response.json()
        results = data.get(results_key, [])

        yield from results

        # Check if there are more pages
        size_info = data.get("size", len(results))
        if size_info < limit:
            break

        start += limit
