"""Command-line interface for the Confluence backup viewer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from atlassian_backup import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="confluence-backup-viewer",
        description="Browse Confluence backup content in a local web browser.",
    )
    parser.add_argument(
        "backup_dir",
        help="Path to the backup directory (must contain backup_manifest.json)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to serve on (default: 5000)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
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

    backup_dir = Path(args.backup_dir).resolve()

    if not backup_dir.is_dir():
        print(f"Error: {backup_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    manifest_path = backup_dir / "backup_manifest.json"
    if not manifest_path.exists():
        print(
            f"Error: backup_manifest.json not found in {backup_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    from atlassian_backup.confluence.viewer.app import create_app

    app = create_app(backup_dir)

    print(f"Serving backup: {backup_dir.name}")
    print(f"Open http://{args.host}:{args.port}/ in your browser")

    app.run(host=args.host, port=args.port, debug=False)
