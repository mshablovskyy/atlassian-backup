"""Tests for confluence.cli module."""

from __future__ import annotations

from atlassian_backup.confluence.cli import build_parser


class TestBuildParser:
    def test_url_argument(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["https://example.com/display/SPACE"])
        assert args.url == "https://example.com/display/SPACE"

    def test_name_option(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["https://example.com/display/SPACE", "--name", "my-backup"])
        assert args.name == "my-backup"

    def test_format_option(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["https://example.com/display/SPACE", "--format", "zip"])
        assert args.output_format == "zip"

    def test_default_format(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["https://example.com/display/SPACE"])
        assert args.output_format == "folder"

    def test_verbose_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["https://example.com/display/SPACE", "--verbose"])
        assert args.verbose is True

    def test_output_dir_option(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["https://example.com/display/SPACE", "--output-dir", "/tmp"])
        assert args.output_dir == "/tmp"

    def test_no_store_raw_response_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["https://example.com/display/SPACE", "--no-store-raw-response"])
        assert args.no_store_raw_response is True

    def test_no_store_raw_response_default(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["https://example.com/display/SPACE"])
        assert args.no_store_raw_response is False
