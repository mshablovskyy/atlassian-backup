"""HTTP client with retry logic for Atlassian REST APIs."""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase
from urllib3.util.retry import Retry


def create_session(auth: AuthBase, timeout: int = 30) -> requests.Session:
    """Create a requests.Session with retry and auth configured.

    Retries on 429 (rate limit) and 5xx server errors with exponential backoff.

    Args:
        auth: Authentication adapter (e.g., BearerTokenAuth).
        timeout: Default request timeout in seconds.

    Returns:
        Configured requests.Session.
    """
    session = requests.Session()
    session.auth = auth

    retry = Retry(
        total=5,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update(
        {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )

    # Store timeout as custom attribute for use by callers
    session.timeout = timeout  # type: ignore[attr-defined]

    return session


def create_write_session(auth: AuthBase, timeout: int = 30) -> requests.Session:
    """Create a requests.Session with retry for write operations.

    Retries on 429 (rate limit) and 5xx server errors with exponential backoff.
    Allows POST and PUT methods in addition to GET and HEAD.

    Args:
        auth: Authentication adapter (e.g., BearerTokenAuth).
        timeout: Default request timeout in seconds.

    Returns:
        Configured requests.Session.
    """
    session = requests.Session()
    session.auth = auth

    retry = Retry(
        total=5,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD", "POST", "PUT"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update(
        {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )

    # Store timeout as custom attribute for use by callers
    session.timeout = timeout  # type: ignore[attr-defined]

    return session


def api_get(
    session: requests.Session,
    url: str,
    params: dict[str, Any] | None = None,
) -> requests.Response:
    """Perform a GET request with the session's default timeout.

    Args:
        session: Configured requests session.
        url: Full URL to request.
        params: Optional query parameters.

    Returns:
        Response object (caller should check status).
    """
    timeout = getattr(session, "timeout", 30)
    return session.get(url, params=params, timeout=timeout)


def api_post(
    session: requests.Session,
    url: str,
    json: dict[str, Any] | list[dict[str, Any]] | None = None,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    files: dict[str, Any] | None = None,
) -> requests.Response:
    """Perform a POST request with the session's default timeout.

    Args:
        session: Configured requests session.
        url: Full URL to request.
        json: Optional JSON body.
        data: Optional raw body data.
        headers: Optional extra headers (merged with session headers).
        files: Optional files for multipart upload.

    Returns:
        Response object (caller should check status).
    """
    timeout = getattr(session, "timeout", 30)
    return session.post(url, json=json, data=data, headers=headers, files=files, timeout=timeout)
