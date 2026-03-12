"""Tests for shared.logging_setup module."""

from __future__ import annotations

import logging
from pathlib import Path

from atlassian_backup.shared.logging_setup import setup_logging


class TestSetupLogging:
    def test_creates_log_directory(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        setup_logging(log_dir)
        assert log_dir.exists()

    def test_creates_app_log_file(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        logger = setup_logging(log_dir)
        logger.info("test message")
        log_file = log_dir / "progress.log"
        assert log_file.exists()
        assert "test message" in log_file.read_text()

    def test_creates_backup_log_file(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        backup_log = tmp_path / "backup" / "progress.log"
        logger = setup_logging(log_dir, backup_log)
        logger.info("backup test")
        assert backup_log.exists()
        assert "backup test" in backup_log.read_text()

    def test_verbose_mode(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        logger = setup_logging(log_dir, verbose=True)
        # Console handler should be at DEBUG level
        console_handler = next(
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        )
        assert console_handler.level == logging.DEBUG
