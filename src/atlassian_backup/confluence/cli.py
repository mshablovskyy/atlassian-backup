"""Command-line interface for Confluence backup."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from atlassian_backup import __version__
from atlassian_backup.confluence.backup_orchestrator import run_backup
from atlassian_backup.confluence.url_parser import parse_confluence_url
from atlassian_backup.shared.config import load_config


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="confluence-backup",
        description="Back up Confluence spaces and pages from Data Center instances.",
    )
    parser.add_argument(
        "url",
        help="Confluence URL to back up (space or page URL)",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Custom backup name (default: auto-generated with timestamp)",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=["folder", "zip"],
        default="folder",
        help="Output format: folder (default) or zip archive",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Parent directory for backup output (default: current directory)",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Path to .env file (default: .env in current directory)",
    )
    parser.add_argument(
        "--no-store-raw-response",
        action="store_true",
        help="Do not store raw_response.json files (saves disk space)",
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
        # Load configuration
        config = load_config(args.env_file)

        # Parse the target URL
        parsed_url = parse_confluence_url(args.url)

        # Run the backup
        result_path, error_count = run_backup(
            config=config,
            parsed_url=parsed_url,
            source_url=args.url,
            output_dir=Path(args.output_dir),
            backup_name=args.name,
            output_format=args.output_format,
            verbose=args.verbose,
            store_raw_response=not args.no_store_raw_response,
        )

        print(f"\nBackup saved to: {result_path}")

        if error_count > 0:
            print(
                f"Backup completed with {error_count} error(s). "
                f"See backup_manifest.json for details.",
                file=sys.stderr,
            )
            sys.exit(1)

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nBackup interrupted by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
