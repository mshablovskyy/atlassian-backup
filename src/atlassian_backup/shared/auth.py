"""Authentication adapters for Atlassian products."""

from __future__ import annotations

from requests.auth import AuthBase
from requests.models import PreparedRequest


class BearerTokenAuth(AuthBase):
    """Bearer token (PAT) authentication for Atlassian Data Center."""

    def __init__(self, token: str) -> None:
        self.token = token

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r
