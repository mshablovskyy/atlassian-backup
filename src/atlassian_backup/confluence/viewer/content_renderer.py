"""Transform Confluence storage format HTML into browser-friendly HTML."""

from __future__ import annotations

import re

from atlassian_backup.confluence.attachment_exporter import sanitize_filename

# Emoticon name -> unicode mapping
_EMOTICONS: dict[str, str] = {
    "smile": "\U0001f642",
    "sad": "\U0001f641",
    "cheeky": "\U0001f61b",
    "laugh": "\U0001f604",
    "wink": "\U0001f609",
    "thumbs-up": "\U0001f44d",
    "thumbs-down": "\U0001f44e",
    "information": "\u2139\ufe0f",
    "tick": "\u2705",
    "cross": "\u274c",
    "warning": "\u26a0\ufe0f",
    "plus": "\u2795",
    "minus": "\u2796",
    "question": "\u2753",
    "light-on": "\U0001f4a1",
    "light-off": "\U0001f4a1",
    "yellow-star": "\u2b50",
    "red-star": "\u2b50",
    "green-star": "\u2b50",
    "blue-star": "\u2b50",
    "heart": "\u2764\ufe0f",
    "broken-heart": "\U0001f494",
}


def render_body(
    body_html: str,
    page_id: str,
    title_to_id: dict[str, str],
) -> str:
    """Transform Confluence storage-format HTML into browser-renderable HTML.

    Processes Confluence-specific tags (ac:*, ri:*) into standard HTML.

    Args:
        body_html: Raw Confluence storage format HTML.
        page_id: Current page ID (for resolving attachment URLs).
        title_to_id: Mapping of lowercase page title to page ID.

    Returns:
        Transformed HTML string.
    """
    html = body_html

    # 1. Images: <ac:image ...><ri:attachment ri:filename="X"/></ac:image>
    html = _transform_images(html, page_id)

    # 2. Code blocks: <ac:structured-macro ac:name="code">
    html = _transform_code_blocks(html)

    # 3. Info/warning/note panels
    html = _transform_panels(html)

    # 4. Status lozenges
    html = _transform_status(html)

    # 5. Internal page links
    html = _transform_page_links(html, title_to_id)

    # 6. User mentions
    html = _transform_user_mentions(html)

    # 7. Inline comment markers - unwrap
    html = _transform_inline_comments(html)

    # 8. Task lists
    html = _transform_task_lists(html)

    # 9. Emoticons
    html = _transform_emoticons(html)

    # 10. Draw.io diagrams -> PNG preview images
    html = _transform_drawio(html, page_id)

    # 11. Known unsupported macros -> placeholder
    html = _transform_placeholder_macros(html)

    # 12. Fallback: strip remaining ac:/ri: tags but keep inner text
    html = _strip_remaining_ac_ri(html)

    return html


def _transform_images(html: str, page_id: str) -> str:
    """Convert ac:image with ri:attachment to <img> tags."""
    pattern = re.compile(
        r'<ac:image[^>]*>.*?<ri:attachment\s+ri:filename="([^"]+)"'
        r"\s*/?\s*>.*?</ac:image>",
        re.DOTALL,
    )

    def _replace(m: re.Match[str]) -> str:
        filename = sanitize_filename(m.group(1))
        return f'<img src="/attachment/{page_id}/{filename}" class="confluence-image">'

    return pattern.sub(_replace, html)


def _transform_code_blocks(html: str) -> str:
    """Convert ac:structured-macro name="code" to <pre><code>."""
    pattern = re.compile(
        r'<ac:structured-macro\s+ac:name="code"[^>]*>'
        r".*?"
        r"<ac:plain-text-body>\s*<!\[CDATA\[(.*?)\]\]>\s*</ac:plain-text-body>"
        r".*?"
        r"</ac:structured-macro>",
        re.DOTALL,
    )

    def _replace(m: re.Match[str]) -> str:
        code = m.group(1)
        return f'<pre class="code-block"><code>{code}</code></pre>'

    return pattern.sub(_replace, html)


def _transform_panels(html: str) -> str:
    """Convert info/warning/note/tip panels to styled divs."""
    for panel_type in ("info", "warning", "note", "tip"):
        pattern = re.compile(
            rf'<ac:structured-macro\s+ac:name="{panel_type}"[^>]*>'
            r".*?"
            r"<ac:rich-text-body>(.*?)</ac:rich-text-body>"
            r".*?"
            r"</ac:structured-macro>",
            re.DOTALL,
        )
        html = pattern.sub(
            rf'<div class="panel-{panel_type}">\1</div>',
            html,
        )
    return html


def _transform_status(html: str) -> str:
    """Convert status macros to styled spans."""
    pattern = re.compile(
        r'<ac:structured-macro\s+ac:name="status"[^>]*>'
        r".*?"
        r'<ac:parameter\s+ac:name="title">(.*?)</ac:parameter>'
        r".*?"
        r"(?:<ac:parameter\s+ac:name=\"colour\">(.*?)</ac:parameter>)?"
        r".*?"
        r"</ac:structured-macro>",
        re.DOTALL,
    )

    def _replace(m: re.Match[str]) -> str:
        title = m.group(1)
        colour = (m.group(2) or "Grey").lower()
        return f'<span class="status-lozenge status-{colour}">{title}</span>'

    return pattern.sub(_replace, html)


def _transform_page_links(html: str, title_to_id: dict[str, str]) -> str:
    """Convert ac:link with ri:page to internal links."""
    pattern = re.compile(
        r"<ac:link>"
        r"\s*<ri:page\s+[^>]*?ri:content-title=\"([^\"]+)\"[^/]*/?\s*>"
        r"(.*?)"
        r"</ac:link>",
        re.DOTALL,
    )

    def _replace(m: re.Match[str]) -> str:
        title = m.group(1)
        inner = m.group(2).strip()
        page_id = title_to_id.get(title.lower())
        display = inner if inner else title
        # Strip any ac:plain-text-link-body from display
        display = re.sub(
            r"<ac:plain-text-link-body>\s*<!\[CDATA\[(.*?)\]\]>"
            r"\s*</ac:plain-text-link-body>",
            r"\1",
            display,
        )
        if page_id:
            return f'<a href="/page/{page_id}">{display}</a>'
        return f'<span class="broken-link" title="Page not in backup">{display}</span>'

    return pattern.sub(_replace, html)


def _transform_user_mentions(html: str) -> str:
    """Convert ri:user mentions to styled spans."""
    pattern = re.compile(
        r"<ac:link>"
        r'\s*<ri:user\s+ri:userkey="([^"]*)"\s*/?\s*>'
        r"(.*?)"
        r"</ac:link>",
        re.DOTALL,
    )

    def _replace(m: re.Match[str]) -> str:
        userkey = m.group(1)
        inner = m.group(2).strip()
        if inner:
            return f'<span class="user-mention">{inner}</span>'
        short_key = userkey[:8] if len(userkey) > 8 else userkey
        return (
            f'<span class="user-mention" '
            f'title="Confluence user: {userkey}">'
            f"[user: {short_key}...]</span>"
        )

    return pattern.sub(_replace, html)


def _transform_inline_comments(html: str) -> str:
    """Unwrap inline comment markers, keeping inner text."""
    html = re.sub(
        r'<ac:inline-comment-marker\s+ac:ref="[^"]*">',
        "",
        html,
    )
    html = html.replace("</ac:inline-comment-marker>", "")
    return html


def _transform_task_lists(html: str) -> str:
    """Convert ac:task-list/ac:task to HTML checkboxes."""
    html = html.replace("<ac:task-list>", '<ul class="task-list">')
    html = html.replace("</ac:task-list>", "</ul>")

    # Transform individual tasks
    pattern = re.compile(
        r"<ac:task>"
        r"\s*<ac:task-id>[^<]*</ac:task-id>"
        r"\s*<ac:task-status>(complete|incomplete)</ac:task-status>"
        r"\s*<ac:task-body>(.*?)</ac:task-body>"
        r"\s*</ac:task>",
        re.DOTALL,
    )

    def _replace(m: re.Match[str]) -> str:
        status = m.group(1)
        body = m.group(2)
        checked = " checked disabled" if status == "complete" else " disabled"
        return f'<li><input type="checkbox"{checked}> {body}</li>'

    html = pattern.sub(_replace, html)
    return html


def _transform_emoticons(html: str) -> str:
    """Convert ac:emoticon to unicode emoji."""
    pattern = re.compile(
        r'<ac:emoticon\s+ac:name="([^"]+)"[^/]*/?\s*>',
    )

    def _replace(m: re.Match[str]) -> str:
        name = m.group(1)
        return _EMOTICONS.get(name, f"[{name}]")

    return pattern.sub(_replace, html)


def _transform_drawio(html: str, page_id: str) -> str:
    """Convert draw.io and inc-drawio macros to inline PNG preview images.

    Confluence stores a PNG preview for each draw.io diagram as an attachment
    named ``{diagramName}.png``. The ``inc-drawio`` variant embeds a diagram
    from another page and includes a ``pageId`` parameter pointing to the
    page that owns the attachment.
    """
    pattern = re.compile(
        r'<ac:structured-macro\s+ac:name="(?:inc-)?drawio"[^>]*>'
        r"(?P<params>.*?)"
        r"</ac:structured-macro>",
        re.DOTALL,
    )

    def _replace(m: re.Match[str]) -> str:
        params = m.group("params")
        name_match = re.search(
            r'<ac:parameter\s+ac:name="diagramName">([^<]+)</ac:parameter>',
            params,
        )
        if not name_match:
            return '<div class="macro-placeholder">[drawio macro]</div>'
        diagram_name = name_match.group(1)

        # inc-drawio stores the attachment on the referenced page
        owner_id = page_id
        pid_match = re.search(
            r'<ac:parameter\s+ac:name="pageId">([^<]+)</ac:parameter>',
            params,
        )
        if pid_match:
            owner_id = pid_match.group(1)

        filename = sanitize_filename(f"{diagram_name}.png")
        return (
            f'<div class="drawio-diagram">'
            f'<img src="/attachment/{owner_id}/{filename}" '
            f'alt="{diagram_name}" class="confluence-image">'
            f"</div>"
        )

    return pattern.sub(_replace, html)


def _transform_placeholder_macros(html: str) -> str:
    """Replace known unsupported macros with placeholder text."""
    for macro_name in ("toc", "jira", "include", "gliffy", "excerpt"):
        pattern = re.compile(
            rf'<ac:structured-macro\s+ac:name="{macro_name}"[^>]*>'
            r".*?"
            r"</ac:structured-macro>",
            re.DOTALL,
        )
        html = pattern.sub(
            f'<div class="macro-placeholder">[{macro_name} macro]</div>',
            html,
        )
    return html


def _strip_remaining_ac_ri(html: str) -> str:
    """Handle any remaining ac:/ri: tags.

    Structured macros are rendered as visible placeholders with the macro name.
    Other ac:/ri: tags are stripped, keeping inner text.
    """
    # Wrap unrecognized structured macros in a visible placeholder
    macro_pattern = re.compile(
        r'<ac:structured-macro\s+ac:name="([^"]*)"[^>]*>'
        r"(.*?)"
        r"</ac:structured-macro>",
        re.DOTALL,
    )
    html = macro_pattern.sub(
        r'<div class="macro-placeholder" title="Unprocessed Confluence macro: \1">'
        r"[\1 macro]</div>",
        html,
    )
    # Remove remaining self-closing tags
    html = re.sub(r"<(?:ac|ri):[^>]*/\s*>", "", html)
    # Remove remaining opening tags
    html = re.sub(r"<(?:ac|ri):[^>]*>", "", html)
    # Remove remaining closing tags
    html = re.sub(r"</(?:ac|ri):[^>]*>", "", html)
    return html
