"""Command-line interface for Confluence restore."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from atlassian_backup import __version__
from atlassian_backup.confluence.restore_orchestrator import run_restore
from atlassian_backup.shared.config import load_config


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="confluence-restore",
        description="Restore Confluence pages from a backup to a Data Center instance.",
    )
    parser.add_argument(
        "backup_dir",
        help="Path to the backup directory (containing backup_manifest.json)",
    )
    parser.add_argument(
        "--space-key",
        required=True,
        help="Target space key to restore into",
    )
    parser.add_argument(
        "--parent-page-id",
        default=None,
        help="Parent page ID under which to restore (default: space root)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be restored without making changes",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume a previously interrupted restore",
    )
    parser.add_argument(
        "--skip-attachments",
        action="store_true",
        help="Skip attachment upload",
    )
    parser.add_argument(
        "--skip-comments",
        action="store_true",
        help="Skip comment creation",
    )
    parser.add_argument(
        "--resolve-userkeys",
        action="store_true",
        help="Replace user references with display names (for cross-instance restores)",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Path to .env file (default: .env in current directory)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        # Validate backup directory
        backup_dir = Path(args.backup_dir)
        if not backup_dir.is_dir():
            raise ValueError(f"Backup directory not found: {backup_dir}")

        # Load configuration (not needed for dry-run but validate early)
        config = load_config(args.env_file)

        # Run the restore
        manifest_path, error_count = run_restore(
            config=config,
            backup_dir=backup_dir,
            space_key=args.space_key,
            parent_page_id=args.parent_page_id,
            dry_run=args.dry_run,
            resume=args.resume,
            skip_attachments=args.skip_attachments,
            skip_comments=args.skip_comments,
            resolve_userkeys=args.resolve_userkeys,
            verbose=args.verbose,
        )

        print(f"\nRestore manifest: {manifest_path}")

        if error_count > 0:
            print(
                f"Restore completed with {error_count} error(s). See manifest for details.",
                file=sys.stderr,
            )
            sys.exit(1)

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nRestore interrupted by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
