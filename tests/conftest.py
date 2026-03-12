"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

from atlassian_backup.shared.auth import BearerTokenAuth
from atlassian_backup.shared.backup_writer import BackupWriter
from atlassian_backup.shared.http_client import create_session


@pytest.fixture
def test_token() -> str:
    return "test-token-12345"


@pytest.fixture
def auth(test_token: str) -> BearerTokenAuth:
    return BearerTokenAuth(test_token)


@pytest.fixture
def session(auth: BearerTokenAuth) -> requests.Session:
    return create_session(auth)


@pytest.fixture
def tmp_backup_dir(tmp_path: Path) -> Path:
    backup_dir = tmp_path / "test-backup"
    backup_dir.mkdir()
    return backup_dir


@pytest.fixture
def writer(tmp_backup_dir: Path) -> BackupWriter:
    return BackupWriter(tmp_backup_dir)
