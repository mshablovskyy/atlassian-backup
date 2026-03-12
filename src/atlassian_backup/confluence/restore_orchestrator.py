"""Main restore coordinator for Confluence."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from atlassian_backup.confluence.blog_restorer import restore_blog_posts
from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.confluence.models import RestoreManifest
from atlassian_backup.confluence.page_restorer import restore_page_tree
from atlassian_backup.confluence.user_resolver import load_user_mapping
from atlassian_backup.confluence.viewer.backup_reader import BackupData
from atlassian_backup.shared.auth import BearerTokenAuth
from atlassian_backup.shared.config import ConfluenceConfig
from atlassian_backup.shared.http_client import create_write_session
from atlassian_backup.shared.logging_setup import setup_logging

logger = logging.getLogger("atlassian_backup")


def _manifest_path_for(backup_dir: Path) -> Path:
    """Return the restore manifest path next to the backup directory.

    Format: {parent}/{backup_dir_name}_restore_manifest.json
    """
    return backup_dir.parent / f"{backup_dir.name}_restore_manifest.json"


def _flush_manifest(manifest: RestoreManifest, path: Path) -> None:
    """Write current manifest state to disk for resume support."""
    path.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _print_dry_run_summary(backup: BackupData) -> None:
    """Print a summary of what would be restored."""
    stats = backup.statistics
    print("\n--- Dry Run Summary ---")
    print(f"Backup: {backup.backup_name}")
    print(f"Type: {backup.backup_type}")
    print(f"Space key: {backup.space_key}")
    print(f"Pages: {stats.get('pages_backed_up', 0)}")
    print(f"Blog posts: {stats.get('blog_posts_backed_up', 0)}")
    print(f"Attachments: {stats.get('attachments_downloaded', 0)}")
    print(f"Comments: {stats.get('comments_backed_up', 0)}")
    print(f"Labels: {stats.get('labels_backed_up', 0)}")

    def _print_tree(nodes: list[dict[str, Any]], depth: int = 0) -> None:
        for node in nodes:
            prefix = "  " * depth + "- "
            print(f"{prefix}{node.get('title', '?')} ({node.get('id', '?')})")
            _print_tree(node.get("children", []), depth + 1)

    print("\nPage tree:")
    _print_tree(backup.page_tree)
    print("--- End of Dry Run ---\n")


def run_restore(
    config: ConfluenceConfig,
    backup_dir: Path,
    space_key: str,
    parent_page_id: str | None = None,
    dry_run: bool = False,
    resume: bool = False,
    skip_attachments: bool = False,
    skip_comments: bool = False,
    resolve_userkeys: bool = False,
    verbose: bool = False,
) -> tuple[Path, int]:
    """Run a full Confluence restore from backup.

    Args:
        config: Confluence connection configuration.
        backup_dir: Path to the backup directory.
        space_key: Target space key to restore into.
        parent_page_id: Optional parent page ID for the restored tree.
        dry_run: If True, only print what would be restored.
        resume: If True, resume from existing restore manifest.
        skip_attachments: Skip attachment upload.
        skip_comments: Skip comment creation.
        resolve_userkeys: Replace user references with display names.
        verbose: Enable verbose logging.

    Returns:
        Tuple of (path to restore manifest, number of errors).
    """
    # Setup logging
    log_dir = Path("logs")
    setup_logging(log_dir, verbose=verbose)

    logger.info("Starting Confluence restore from: %s", backup_dir)

    # Load backup data
    backup = BackupData.load(backup_dir)
    logger.info(
        "Backup loaded: %s (%d pages, %d blog posts)",
        backup.backup_name,
        backup.statistics.get("pages_backed_up", 0),
        backup.statistics.get("blog_posts_backed_up", 0),
    )

    # Dry run: just print summary and exit
    if dry_run:
        _print_dry_run_summary(backup)
        return _manifest_path_for(backup_dir), 0

    # Create HTTP session with write support
    auth = BearerTokenAuth(config.token)
    session = create_write_session(auth)
    client = ConfluenceClient(session, config.base_url)

    # Verify connection
    try:
        client.verify_connection()
    except Exception as e:
        logger.error("Failed to connect to Confluence: %s", e)
        raise

    # Validate target space exists
    try:
        client.get_space(space_key)
        logger.info("Target space verified: %s", space_key)
    except Exception as e:
        logger.error("Target space '%s' not accessible: %s", space_key, e)
        raise ValueError(f"Target space '{space_key}' not accessible: {e}") from e

    # Initialize or load restore manifest
    manifest_path = _manifest_path_for(backup_dir)

    if resume and manifest_path.exists():
        logger.info("Resuming from existing restore manifest: %s", manifest_path)
        with open(manifest_path) as f:
            manifest_data = json.load(f)
        manifest = RestoreManifest.from_dict(manifest_data)
        logger.info(
            "Resume state: %d pages already restored, %d in id_mapping",
            manifest.pages_restored,
            len(manifest.id_mapping),
        )
    else:
        manifest = RestoreManifest(
            backup_name=backup.backup_name,
            target_space_key=space_key,
            target_base_url=config.base_url,
            parent_page_id=parent_page_id,
        )

    # Load user mapping if requested
    user_mapping: dict[str, str] | None = None
    if resolve_userkeys:
        user_mapping = load_user_mapping(backup_dir)
        if user_mapping:
            logger.info("Loaded %d user mapping(s) for userkey resolution", len(user_mapping))
        else:
            logger.warning("--resolve-userkeys enabled but no users.json found in backup")

    def flush() -> None:
        _flush_manifest(manifest, manifest_path)

    # Restore page tree
    if backup.page_tree:
        logger.info("Restoring page tree (%d root nodes)", len(backup.page_tree))
        restore_page_tree(
            client,
            backup,
            backup.page_tree,
            space_key,
            parent_page_id,
            manifest,
            skip_attachments=skip_attachments,
            skip_comments=skip_comments,
            flush_callback=flush,
            user_mapping=user_mapping,
        )

    # Restore blog posts (if space backup)
    if backup.backup_type == "space":
        restore_blog_posts(
            client,
            backup,
            space_key,
            manifest,
            skip_attachments=skip_attachments,
            user_mapping=user_mapping,
        )

    # Record user resolution count
    if user_mapping:
        manifest.users_resolved = len(user_mapping)

    # Write final manifest
    _flush_manifest(manifest, manifest_path)

    logger.info("Restore complete: %s", backup.backup_name)
    logger.info(
        "Stats: %d pages, %d blogs, %d attachments, %d comments, %d labels, %d users, %d errors",
        manifest.pages_restored,
        manifest.blog_posts_restored,
        manifest.attachments_uploaded,
        manifest.comments_restored,
        manifest.labels_restored,
        manifest.users_resolved,
        len(manifest.errors),
    )

    return manifest_path, len(manifest.errors)
