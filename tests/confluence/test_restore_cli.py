"""Tests for confluence.restore_cli module."""

from __future__ import annotations

from atlassian_backup.confluence.restore_cli import build_parser


class TestBuildParser:
    def test_backup_dir_argument(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["./output/my-backup", "--space-key", "DEV"])
        assert args.backup_dir == "./output/my-backup"

    def test_space_key_required(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["./output/my-backup", "--space-key", "NEWSPACE"])
        assert args.space_key == "NEWSPACE"

    def test_parent_page_id_option(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["./output/my-backup", "--space-key", "DEV", "--parent-page-id", "12345"]
        )
        assert args.parent_page_id == "12345"

    def test_parent_page_id_default(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["./output/my-backup", "--space-key", "DEV"])
        assert args.parent_page_id is None

    def test_dry_run_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["./output/my-backup", "--space-key", "DEV", "--dry-run"])
        assert args.dry_run is True

    def test_resume_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["./output/my-backup", "--space-key", "DEV", "--resume"])
        assert args.resume is True

    def test_skip_attachments_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["./output/my-backup", "--space-key", "DEV", "--skip-attachments"])
        assert args.skip_attachments is True

    def test_skip_comments_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["./output/my-backup", "--space-key", "DEV", "--skip-comments"])
        assert args.skip_comments is True

    def test_verbose_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["./output/my-backup", "--space-key", "DEV", "--verbose"])
        assert args.verbose is True

    def test_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["./output/my-backup", "--space-key", "DEV"])
        assert args.dry_run is False
        assert args.resume is False
        assert args.skip_attachments is False
        assert args.skip_comments is False
        assert args.verbose is False
        assert args.env_file is None
