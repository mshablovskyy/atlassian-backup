"""Tests for confluence.attachment_exporter module."""

from __future__ import annotations

from atlassian_backup.confluence.attachment_exporter import sanitize_filename


class TestSanitizeFilename:
    def test_normal_filename(self) -> None:
        assert sanitize_filename("report.pdf") == "report.pdf"

    def test_special_characters(self) -> None:
        result = sanitize_filename('my<file>:name/"test"')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result

    def test_long_filename(self) -> None:
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name)
        assert len(result) <= 200

    def test_collapses_underscores(self) -> None:
        result = sanitize_filename("a:::b")
        assert result == "a_b"
