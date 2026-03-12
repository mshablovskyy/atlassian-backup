"""Tests for confluence.viewer.cli module."""

from __future__ import annotations

from atlassian_backup.confluence.viewer.cli import build_parser


class TestBuildParser:
    def test_backup_dir_argument(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["/path/to/backup"])
        assert args.backup_dir == "/path/to/backup"

    def test_port_option(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["/path/to/backup", "--port", "8080"])
        assert args.port == 8080

    def test_default_port(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["/path/to/backup"])
        assert args.port == 5000

    def test_host_option(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["/path/to/backup", "--host", "0.0.0.0"])
        assert args.host == "0.0.0.0"

    def test_default_host(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["/path/to/backup"])
        assert args.host == "127.0.0.1"
