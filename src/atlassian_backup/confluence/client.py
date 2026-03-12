"""Confluence REST API client for Data Center instances."""

from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any

import requests

from atlassian_backup.shared.http_client import api_get, api_post
from atlassian_backup.shared.pagination import paginated_get

logger = logging.getLogger("atlassian_backup")


def _raise_for_status_verbose(response: requests.Response) -> None:
    """Like response.raise_for_status() but includes the response body."""
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        body = response.text[:500] if response.text else ""
        raise requests.HTTPError(f"{e} — {body}", response=response) from e


# Expand parameters for getting full page data
PAGE_EXPAND = "body.storage,version,ancestors,metadata.labels,space,history"
BLOG_EXPAND = "body.storage,version,space,history"


class ConfluenceClient:
    """Thin wrapper around Confluence REST API v2 (Server/DC compatible)."""

    def __init__(self, session: requests.Session, base_url: str) -> None:
        self.session = session
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/rest/api"

    def get_space(self, space_key: str) -> dict[str, Any]:
        """Get space metadata.

        Args:
            space_key: The space key (e.g., "MYSPACE").

        Returns:
            Space metadata dict.

        Raises:
            requests.HTTPError: On non-200 response.
        """
        url = f"{self.api_url}/space/{space_key}"
        response = api_get(self.session, url, params={"expand": "description.plain,homepage"})
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    def get_page(self, page_id: str) -> dict[str, Any]:
        """Get a single page with full content and metadata.

        Args:
            page_id: The page ID.

        Returns:
            Full page data dict.

        Raises:
            requests.HTTPError: On non-200 response.
        """
        url = f"{self.api_url}/content/{page_id}"
        response = api_get(self.session, url, params={"expand": PAGE_EXPAND})
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    def get_page_by_title(self, space_key: str, title: str) -> dict[str, Any] | None:
        """Find a page by space key and title.

        Args:
            space_key: The space key.
            title: Exact page title.

        Returns:
            Page data dict or None if not found.
        """
        url = f"{self.api_url}/content"
        params = {
            "spaceKey": space_key,
            "title": title,
            "expand": PAGE_EXPAND,
        }
        response = api_get(self.session, url, params=params)
        response.raise_for_status()
        results = response.json().get("results", [])
        return results[0] if results else None

    def get_child_pages(self, page_id: str) -> Generator[dict[str, Any], None, None]:
        """Get all child pages of a given page (paginated).

        Args:
            page_id: Parent page ID.

        Yields:
            Child page data dicts (summary only, not expanded).
        """
        url = f"{self.api_url}/content/{page_id}/child/page"
        yield from paginated_get(self.session, url, params={"expand": "version"})

    def get_page_labels(self, page_id: str) -> list[dict[str, Any]]:
        """Get labels for a page.

        Args:
            page_id: The page ID.

        Returns:
            List of label dicts.
        """
        return list(
            paginated_get(
                self.session,
                f"{self.api_url}/content/{page_id}/label",
            )
        )

    def get_page_comments(self, page_id: str) -> Generator[dict[str, Any], None, None]:
        """Get all comments on a page (paginated).

        Args:
            page_id: The page ID.

        Yields:
            Comment data dicts.
        """
        url = f"{self.api_url}/content/{page_id}/child/comment"
        yield from paginated_get(
            self.session,
            url,
            params={"expand": "body.storage,version,history"},
        )

    def get_page_attachments(self, page_id: str) -> Generator[dict[str, Any], None, None]:
        """Get all attachments on a page (paginated).

        Args:
            page_id: The page ID.

        Yields:
            Attachment metadata dicts.
        """
        url = f"{self.api_url}/content/{page_id}/child/attachment"
        yield from paginated_get(self.session, url)

    def download_attachment(self, download_url: str) -> requests.Response:
        """Download an attachment binary.

        Args:
            download_url: Relative or absolute download URL from attachment metadata.

        Returns:
            Response with binary content.
        """
        if download_url.startswith("/"):
            full_url = f"{self.base_url}{download_url}"
        else:
            full_url = download_url

        timeout = getattr(self.session, "timeout", 60)
        response = self.session.get(full_url, timeout=timeout, stream=True)
        response.raise_for_status()
        return response

    def get_space_pages(self, space_key: str) -> Generator[dict[str, Any], None, None]:
        """Get all pages in a space (paginated).

        Args:
            space_key: The space key.

        Yields:
            Page data dicts.
        """
        url = f"{self.api_url}/content"
        yield from paginated_get(
            self.session,
            url,
            params={"spaceKey": space_key, "type": "page", "expand": "version"},
        )

    def get_space_blog_posts(self, space_key: str) -> Generator[dict[str, Any], None, None]:
        """Get all blog posts in a space (paginated).

        Args:
            space_key: The space key.

        Yields:
            Blog post data dicts.
        """
        url = f"{self.api_url}/content"
        yield from paginated_get(
            self.session,
            url,
            params={"spaceKey": space_key, "type": "blogpost", "expand": BLOG_EXPAND},
        )

    # ── Write operations (for restore) ──────────────────────────────

    def create_page(
        self,
        space_key: str,
        title: str,
        body_storage: str,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new page in a space.

        Args:
            space_key: Target space key.
            title: Page title.
            body_storage: Page body in Confluence storage format.
            parent_id: Optional parent page ID (for nesting).

        Returns:
            Created page data dict (includes new ID).

        Raises:
            requests.HTTPError: On non-200 response.
        """
        payload: dict[str, Any] = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": body_storage,
                    "representation": "storage",
                }
            },
        }
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]

        url = f"{self.api_url}/content"
        response = api_post(self.session, url, json=payload)
        _raise_for_status_verbose(response)
        return response.json()  # type: ignore[no-any-return]

    def create_blog_post(
        self,
        space_key: str,
        title: str,
        body_storage: str,
    ) -> dict[str, Any]:
        """Create a new blog post in a space.

        Args:
            space_key: Target space key.
            title: Blog post title.
            body_storage: Body in Confluence storage format.

        Returns:
            Created blog post data dict.

        Raises:
            requests.HTTPError: On non-200 response.
        """
        payload: dict[str, Any] = {
            "type": "blogpost",
            "title": title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": body_storage,
                    "representation": "storage",
                }
            },
        }

        url = f"{self.api_url}/content"
        response = api_post(self.session, url, json=payload)
        _raise_for_status_verbose(response)
        return response.json()  # type: ignore[no-any-return]

    def add_labels(self, content_id: str, labels: list[str]) -> None:
        """Add labels to a page or blog post.

        Args:
            content_id: The content ID.
            labels: List of label names to add.

        Raises:
            requests.HTTPError: On non-200 response.
        """
        if not labels:
            return
        url = f"{self.api_url}/content/{content_id}/label"
        payload = [{"prefix": "global", "name": label} for label in labels]
        response = api_post(self.session, url, json=payload)
        _raise_for_status_verbose(response)

    def upload_attachment(
        self,
        content_id: str,
        filename: str,
        data: bytes,
        media_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        """Upload an attachment to a page or blog post.

        If an attachment with the same filename already exists (e.g. Confluence
        auto-created a stub from a body reference), the existing attachment is
        updated instead.

        Args:
            content_id: The content ID to attach to.
            filename: Attachment filename.
            data: Binary content.
            media_type: MIME type of the attachment.

        Returns:
            Created/updated attachment data dict.

        Raises:
            requests.HTTPError: On non-200 response.
        """
        response = self._post_attachment(content_id, filename, data, media_type)

        if response.status_code == 400 and "same file name" in response.text:
            logger.debug(
                "Attachment '%s' already exists on %s, updating instead",
                filename,
                content_id,
            )
            existing_id = self._find_attachment_id(content_id, filename)
            if existing_id:
                return self._update_attachment(content_id, existing_id, filename, data, media_type)
            # Could not find it — raise original error
            logger.warning(
                "Attachment '%s' reported as duplicate but not found on page %s",
                filename,
                content_id,
            )

        _raise_for_status_verbose(response)
        return response.json()  # type: ignore[no-any-return]

    def _post_attachment(
        self,
        content_id: str,
        filename: str,
        data: bytes,
        media_type: str,
    ) -> requests.Response:
        """POST a file to the attachment endpoint (low-level)."""
        url = f"{self.api_url}/content/{content_id}/child/attachment"
        files = {"file": (filename, data, media_type)}
        headers = {"X-Atlassian-Token": "nocheck"}
        timeout = getattr(self.session, "timeout", 60)
        original_ct = self.session.headers.pop("Content-Type", None)
        try:
            response = self.session.post(url, files=files, headers=headers, timeout=timeout)
        finally:
            if original_ct is not None:
                self.session.headers["Content-Type"] = original_ct
        return response

    def _find_attachment_id(self, content_id: str, filename: str) -> str | None:
        """Find an existing attachment ID by filename on a page."""
        url = f"{self.api_url}/content/{content_id}/child/attachment"
        params = {"filename": filename}
        response = api_get(self.session, url, params=params)
        if response.status_code != 200:
            return None
        results = response.json().get("results", [])
        return results[0]["id"] if results else None

    def _update_attachment(
        self,
        content_id: str,
        attachment_id: str,
        filename: str,
        data: bytes,
        media_type: str,
    ) -> dict[str, Any]:
        """Update an existing attachment's data."""
        url = f"{self.api_url}/content/{content_id}/child/attachment/{attachment_id}/data"
        files = {"file": (filename, data, media_type)}
        headers = {"X-Atlassian-Token": "nocheck"}
        timeout = getattr(self.session, "timeout", 60)
        original_ct = self.session.headers.pop("Content-Type", None)
        try:
            response = self.session.post(url, files=files, headers=headers, timeout=timeout)
        finally:
            if original_ct is not None:
                self.session.headers["Content-Type"] = original_ct
        _raise_for_status_verbose(response)
        return response.json()  # type: ignore[no-any-return]

    def add_comment(
        self,
        content_id: str,
        body_storage: str,
    ) -> dict[str, Any]:
        """Add a comment to a page or blog post.

        Args:
            content_id: The content ID to comment on.
            body_storage: Comment body in Confluence storage format.

        Returns:
            Created comment data dict.

        Raises:
            requests.HTTPError: On non-200 response.
        """
        payload: dict[str, Any] = {
            "type": "comment",
            "container": {"id": content_id, "type": "page"},
            "body": {
                "storage": {
                    "value": body_storage,
                    "representation": "storage",
                }
            },
        }
        url = f"{self.api_url}/content"
        response = api_post(self.session, url, json=payload)
        _raise_for_status_verbose(response)
        return response.json()  # type: ignore[no-any-return]

    def get_user_by_key(self, user_key: str) -> dict[str, Any] | None:
        """Get a user by their userkey.

        Args:
            user_key: Confluence user key.

        Returns:
            User data dict or None if not found / on error.
        """
        url = f"{self.api_url}/user"
        try:
            response = api_get(self.session, url, params={"key": user_key})
            if response.status_code == 200:
                return response.json()  # type: ignore[no-any-return]
            logger.debug("User lookup failed for key %s: HTTP %d", user_key, response.status_code)
            return None
        except Exception:
            logger.debug("User lookup error for key %s", user_key, exc_info=True)
            return None

    def verify_connection(self) -> bool:
        """Verify connectivity and authentication.

        Returns:
            True if connection is successful.

        Raises:
            requests.HTTPError: On authentication failure.
        """
        url = f"{self.api_url}/space"
        response = api_get(self.session, url, params={"limit": 1})
        if response.status_code == 401:
            raise requests.HTTPError(
                "Authentication failed (401). Check your Personal Access Token.",
                response=response,
            )
        response.raise_for_status()
        logger.info("Connection verified: %s", self.base_url)
        return True
