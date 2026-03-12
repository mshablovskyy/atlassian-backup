"""Tests for confluence.user_resolver module."""

from __future__ import annotations

import json
from pathlib import Path

from atlassian_backup.confluence.user_resolver import (
    load_user_mapping,
    resolve_user_references,
)


class TestLoadUserMapping:
    def test_load_existing_file(self, tmp_path: Path) -> None:
        mapping = {"key1": "Alice", "key2": "Bob"}
        (tmp_path / "users.json").write_text(json.dumps(mapping))
        result = load_user_mapping(tmp_path)
        assert result == mapping

    def test_missing_file(self, tmp_path: Path) -> None:
        result = load_user_mapping(tmp_path)
        assert result == {}

    def test_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / "users.json").write_text("not json")
        result = load_user_mapping(tmp_path)
        assert result == {}

    def test_non_dict_json(self, tmp_path: Path) -> None:
        (tmp_path / "users.json").write_text(json.dumps(["a", "b"]))
        result = load_user_mapping(tmp_path)
        assert result == {}


class TestResolveUserReferences:
    def test_known_user(self) -> None:
        body = '<p>Hello <ac:link><ri:user ri:userkey="key-alice" /></ac:link></p>'
        mapping = {"key-alice": "Alice Smith"}
        result = resolve_user_references(body, mapping)
        assert result == "<p>Hello @Alice Smith</p>"

    def test_unknown_user(self) -> None:
        body = '<ac:link><ri:user ri:userkey="abcdef1234567890" /></ac:link>'
        mapping = {}
        result = resolve_user_references(body, mapping)
        assert result == "@[user:abcdef12...]"

    def test_short_unknown_key(self) -> None:
        body = '<ac:link><ri:user ri:userkey="short" /></ac:link>'
        mapping = {}
        result = resolve_user_references(body, mapping)
        assert result == "@[user:short...]"

    def test_multiple_users(self) -> None:
        body = (
            '<ac:link><ri:user ri:userkey="k1" /></ac:link> and '
            '<ac:link><ri:user ri:userkey="k2" /></ac:link>'
        )
        mapping = {"k1": "Alice", "k2": "Bob"}
        result = resolve_user_references(body, mapping)
        assert result == "@Alice and @Bob"

    def test_empty_body(self) -> None:
        result = resolve_user_references("", {"k1": "Alice"})
        assert result == ""

    def test_no_user_references(self) -> None:
        body = "<p>No user mentions here</p>"
        mapping = {"k1": "Alice"}
        result = resolve_user_references(body, mapping)
        assert result == body

    def test_self_closing_without_space(self) -> None:
        body = '<ac:link><ri:user ri:userkey="k1"/></ac:link>'
        mapping = {"k1": "Alice"}
        result = resolve_user_references(body, mapping)
        assert result == "@Alice"

    def test_with_inner_content(self) -> None:
        """User mention with inner content between ri:user and closing ac:link."""
        body = '<ac:link><ri:user ri:userkey="k1" />some text</ac:link>'
        mapping = {"k1": "Alice"}
        result = resolve_user_references(body, mapping)
        assert result == "@Alice"
