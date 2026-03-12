"""Dual logging setup: application logs directory + backup directory."""

from __future__ import annotations

import logging
from pathlib import Path


def setup_logging(
    app_log_dir: Path,
    backup_log_path: Path | None = None,
    verbose: bool = False,
) -> logging.Logger:
    """Configure dual logging: file in app_log_dir + optional backup dir copy.

    Args:
        app_log_dir: Directory for application logs (e.g., ./logs/).
        backup_log_path: Optional path for log file inside backup output.
        verbose: If True, set console to DEBUG level.

    Returns:
        Root logger configured with handlers.
    """
    app_log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("atlassian_backup")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # App log file handler
    app_log_file = app_log_dir / "progress.log"
    file_handler = logging.FileHandler(app_log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Backup directory log file handler
    if backup_log_path:
        backup_log_path.parent.mkdir(parents=True, exist_ok=True)
        backup_handler = logging.FileHandler(backup_log_path, encoding="utf-8")
        backup_handler.setLevel(logging.DEBUG)
        backup_handler.setFormatter(formatter)
        logger.addHandler(backup_handler)

    return logger
