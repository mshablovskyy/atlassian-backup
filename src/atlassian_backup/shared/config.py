"""Configuration loading from environment variables and .env files."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


@dataclass(frozen=True)
class ConfluenceConfig:
    """Configuration for Confluence Data Center connection."""

    base_url: str
    token: str

    def __post_init__(self) -> None:
        if not self.base_url:
            raise ValueError("CONFLUENCE_BASE is required")
        if not self.token:
            raise ValueError("CONFLUENCE_TOKEN is required")


def load_config(env_file: str | None = None) -> ConfluenceConfig:
    """Load configuration from .env file and environment variables.

    Args:
        env_file: Path to .env file. Defaults to .env in current directory.

    Returns:
        ConfluenceConfig with validated settings.
    """
    env_path = Path(env_file) if env_file else Path(".env")
    if env_path.exists():
        load_dotenv(env_path)
    elif env_file:
        print(f"Error: specified env file not found: {env_path}", file=sys.stderr)
        sys.exit(1)

    base_url = os.getenv("CONFLUENCE_BASE", "").strip().strip('"').strip("'").rstrip("/")
    token = os.getenv("CONFLUENCE_TOKEN", "").strip().strip('"').strip("'")

    if base_url:
        parsed = urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            print(
                f"Error: CONFLUENCE_BASE must be a valid URL with scheme"
                f" (e.g. https://confluence.example.com): {base_url}",
                file=sys.stderr,
            )
            sys.exit(1)

    return ConfluenceConfig(base_url=base_url, token=token)
