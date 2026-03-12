"""Flask application factory and routes for the backup viewer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, abort, render_template, send_file

from atlassian_backup.confluence.attachment_exporter import sanitize_filename
from atlassian_backup.confluence.viewer.backup_reader import BackupData
from atlassian_backup.confluence.viewer.content_renderer import render_body


def _is_ancestor(nodes: list[dict[str, Any]], target_id: str) -> bool:
    """Check if target_id exists anywhere in the tree rooted at nodes."""
    for node in nodes:
        if node.get("id") == target_id:
            return True
        if _is_ancestor(node.get("children", []), target_id):
            return True
    return False


def _filesizeformat(size: int | float) -> str:
    """Format a file size in human-readable form."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size) < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def create_app(backup_dir: Path) -> Flask:
    """Create and configure the Flask viewer application.

    Args:
        backup_dir: Path to the backup directory.

    Returns:
        Configured Flask application.
    """
    backup = BackupData.load(backup_dir)
    title_index = backup.build_title_index()

    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )

    # Register Jinja2 helpers
    app.jinja_env.globals["is_ancestor"] = _is_ancestor
    app.jinja_env.filters["filesizeformat"] = _filesizeformat

    @app.route("/")
    def home() -> str:
        return render_template(
            "home.html",
            backup=backup,
        )

    @app.route("/page/<page_id>")
    def page_view(page_id: str) -> str:
        page_data = backup.get_page(page_id)
        if page_data is None:
            abort(404)

        body_html = render_body(
            page_data.get("body_storage", ""),
            page_id,
            title_index,
        )
        comments = backup.get_comments(page_id)
        # Render comment bodies too
        rendered_comments = []
        for comment in comments:
            rendered_comment = dict(comment)
            rendered_comment["body_rendered"] = render_body(
                comment.get("body_storage", ""),
                page_id,
                title_index,
            )
            rendered_comments.append(rendered_comment)

        attachments = backup.get_attachments_meta(page_id)

        return render_template(
            "page.html",
            backup=backup,
            page=page_data,
            page_id=page_id,
            body_html=body_html,
            comments=rendered_comments,
            attachments=attachments,
            sanitize_filename=sanitize_filename,
        )

    @app.route("/attachment/<page_id>/<filename>")
    def serve_attachment(page_id: str, filename: str) -> Any:
        path = backup.get_attachment_path(page_id, filename)
        if path is None:
            abort(404)
        return send_file(path)

    return app
