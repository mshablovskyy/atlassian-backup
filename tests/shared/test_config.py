"""Tests for shared.config module."""

from __future__ import annotations

import pytest

from atlassian_backup.shared.config import ConfluenceConfig, load_config


class TestConfluenceConfig:
    def test_valid_config(self) -> None:
        config = ConfluenceConfig(base_url="https://example.com", token="abc123")
        assert config.base_url == "https://example.com"
        assert config.token == "abc123"

    def test_empty_base_url_raises(self) -> None:
        with pytest.raises(ValueError, match="CONFLUENCE_BASE is required"):
            ConfluenceConfig(base_url="", token="abc123")

    def test_empty_token_raises(self) -> None:
        with pytest.raises(ValueError, match="CONFLUENCE_TOKEN is required"):
            ConfluenceConfig(base_url="https://example.com", token="")


class TestLoadConfig:
    def test_load_from_env_file(self, tmp_path: object) -> None:
        from pathlib import Path

        env_file = Path(str(tmp_path)) / ".env"
        env_file.write_text(
            'CONFLUENCE_BASE="https://test.example.com"\nCONFLUENCE_TOKEN="test-token"\n'
        )
        config = load_config(str(env_file))
        assert config.base_url == "https://test.example.com"
        assert config.token == "test-token"

    def test_load_from_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CONFLUENCE_BASE", "https://env.example.com")
        monkeypatch.setenv("CONFLUENCE_TOKEN", "env-token")
        # Use a non-existent file so it falls back to env vars
        config = load_config()
        assert config.base_url == "https://env.example.com"
        assert config.token == "env-token"

    def test_strips_trailing_slash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CONFLUENCE_BASE", "https://example.com/")
        monkeypatch.setenv("CONFLUENCE_TOKEN", "token")
        config = load_config()
        assert config.base_url == "https://example.com"

    def test_missing_env_file_exits(self) -> None:
        with pytest.raises(SystemExit):
            load_config("/nonexistent/path/.env")
