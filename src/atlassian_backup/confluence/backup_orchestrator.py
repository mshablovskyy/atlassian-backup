"""Main backup coordinator for Confluence."""

from __future__ import annotations

import logging
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from atlassian_backup.confluence.blog_exporter import export_blog_posts
from atlassian_backup.confluence.client import ConfluenceClient
from atlassian_backup.confluence.models import BackupManifest
from atlassian_backup.confluence.page_exporter import export_page
from atlassian_backup.confluence.space_exporter import export_space_metadata
from atlassian_backup.confluence.url_parser import ParsedConfluenceUrl
from atlassian_backup.confluence.user_collector import collect_users
from atlassian_backup.shared.auth import BearerTokenAuth
from atlassian_backup.shared.backup_writer import BackupWriter
from atlassian_backup.shared.config import ConfluenceConfig
from atlassian_backup.shared.http_client import create_session
from atlassian_backup.shared.logging_setup import setup_logging
from atlassian_backup.shared.url_parser import extract_base_url

logger = logging.getLogger("atlassian_backup")


def _generate_backup_name(custom_name: str | None = None) -> str:
    """Generate a backup directory name."""
    if custom_name:
        return custom_name
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d%H%M")
    short_id = uuid.uuid4().hex[:8]
    return f"confluence-export-{timestamp}-{short_id}"


def run_backup(
    config: ConfluenceConfig,
    parsed_url: ParsedConfluenceUrl,
    source_url: str,
    output_dir: Path,
    backup_name: str | None = None,
    output_format: str = "folder",
    verbose: bool = False,
    store_raw_response: bool = True,
) -> tuple[Path, int]:
    """Run a full Confluence backup.

    Args:
        config: Confluence connection configuration.
        parsed_url: Parsed target URL information.
        source_url: Original source URL (for manifest).
        output_dir: Parent directory for backup output.
        backup_name: Custom backup name (or auto-generated).
        output_format: "folder" or "zip".
        verbose: Enable verbose logging.
        store_raw_response: Write raw_response.json for each page/blog.

    Returns:
        Tuple of (path to backup output, number of errors).
    """
    name = _generate_backup_name(backup_name)

    # When outputting ZIP, write intermediate files to a temp directory on the
    # local filesystem. This avoids shutil.rmtree failures on Docker-mounted
    # volumes where filesystem sync can lag behind file deletions.
    use_zip = output_format == "zip"
    if use_zip:
        temp_dir = Path(tempfile.mkdtemp())
        backup_dir = temp_dir / name
        zip_destination = output_dir / f"{name}.zip"
    else:
        backup_dir = output_dir / name

    # Setup logging with backup directory log
    log_dir = Path("logs")
    backup_log_path = backup_dir / "progress.log"
    setup_logging(log_dir, backup_log_path, verbose=verbose)

    logger.info("Starting Confluence backup: %s", name)
    logger.info("Target: %s (%s)", source_url, parsed_url.target_type)

    # Create HTTP session
    auth = BearerTokenAuth(config.token)
    session = create_session(auth)

    # Determine base URL from config or source URL
    base_url = config.base_url or extract_base_url(source_url)
    client = ConfluenceClient(session, base_url)

    # Verify connection
    try:
        client.verify_connection()
    except Exception as e:
        logger.error("Failed to connect to Confluence: %s", e)
        raise

    writer = BackupWriter(backup_dir)

    manifest = BackupManifest(
        backup_name=name,
        backup_type=parsed_url.target_type,
        source_url=source_url,
        space_key=parsed_url.space_key,
        root_page_id=parsed_url.page_id,
    )

    if parsed_url.target_type == "space":
        _backup_space(client, writer, parsed_url, manifest)
    else:
        _backup_page(client, writer, parsed_url, manifest)

    # Collect user mappings (reads raw_response.json files)
    collect_users(client, writer, manifest)

    # Remove raw_response.json files if requested
    if not store_raw_response:
        _remove_raw_responses(backup_dir)

    # Write manifest
    writer.write_json("backup_manifest.json", manifest.to_dict())

    logger.info("Backup complete: %s", name)
    logger.info(
        "Stats: %d pages, %d blogs, %d attachments, %d comments, %d labels, %d users, %d errors",
        manifest.pages_backed_up,
        manifest.blog_posts_backed_up,
        manifest.attachments_downloaded,
        manifest.comments_backed_up,
        manifest.labels_backed_up,
        manifest.users_collected,
        len(manifest.errors),
    )

    error_count = len(manifest.errors)

    if use_zip:
        return writer.create_zip(destination=zip_destination), error_count

    return backup_dir, error_count


def _remove_raw_responses(backup_dir: Path) -> None:
    """Delete all raw_response.json files from the backup directory."""
    count = 0
    for subdir in ("pages", "blog_posts"):
        parent = backup_dir / subdir
        if not parent.exists():
            continue
        for raw_file in parent.glob("*/raw_response.json"):
            raw_file.unlink()
            count += 1
    logger.info("Removed %d raw_response.json file(s)", count)


def _backup_space(
    client: ConfluenceClient,
    writer: BackupWriter,
    parsed_url: ParsedConfluenceUrl,
    manifest: BackupManifest,
) -> None:
    """Back up an entire Confluence space."""
    space_key = parsed_url.space_key
    if not space_key:
        raise ValueError("Space key is required for space backup")

    # Export space metadata
    space_meta = export_space_metadata(client, writer, space_key)

    # Export pages starting from homepage (recursive)
    homepage_id = space_meta.get("homepage_id")
    if homepage_id:
        logger.info("Starting page tree export from homepage: %s", homepage_id)
        tree = export_page(client, writer, homepage_id, manifest)
        if tree:
            manifest.page_tree.append(tree)
    else:
        # Fall back to listing all pages if no homepage
        logger.info("No homepage found, exporting all space pages individually")
        for page_summary in client.get_space_pages(space_key):
            page_id = page_summary["id"]
            tree = export_page(client, writer, page_id, manifest)
            if tree:
                manifest.page_tree.append(tree)

    # Export blog posts
    export_blog_posts(client, writer, space_key, manifest)


def _backup_page(
    client: ConfluenceClient,
    writer: BackupWriter,
    parsed_url: ParsedConfluenceUrl,
    manifest: BackupManifest,
) -> None:
    """Back up a single page and all its descendants."""
    page_id = parsed_url.page_id

    # If we have a title but no ID, look it up
    if not page_id and parsed_url.space_key and parsed_url.page_title:
        logger.info(
            "Looking up page by title: '%s' in space '%s'",
            parsed_url.page_title,
            parsed_url.space_key,
        )
        page_data = client.get_page_by_title(parsed_url.space_key, parsed_url.page_title)
        if not page_data:
            raise ValueError(
                f"Page not found: '{parsed_url.page_title}' in space '{parsed_url.space_key}'"
            )
        page_id = page_data["id"]

    if not page_id:
        raise ValueError("Could not determine page ID from URL")

    manifest.root_page_id = page_id
    tree = export_page(client, writer, page_id, manifest)
    if tree:
        manifest.page_tree.append(tree)
