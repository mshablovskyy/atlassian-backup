"""Tests for confluence.viewer.content_renderer module."""

from __future__ import annotations

from atlassian_backup.confluence.viewer.content_renderer import render_body


class TestRenderImages:
    def test_image_with_attachment(self) -> None:
        html = '<ac:image ac:height="400"><ri:attachment ri:filename="pic.png" /></ac:image>'
        result = render_body(html, "123", {})
        assert '<img src="/attachment/123/pic.png"' in result
        assert "ac:image" not in result

    def test_image_filename_sanitized(self) -> None:
        html = '<ac:image><ri:attachment ri:filename="my file?.png" /></ac:image>'
        result = render_body(html, "123", {})
        assert '<img src="/attachment/123/my file_.png"' in result


class TestRenderCodeBlocks:
    def test_code_block(self) -> None:
        html = (
            '<ac:structured-macro ac:name="code">'
            "<ac:plain-text-body><![CDATA[print('hello')]]></ac:plain-text-body>"
            "</ac:structured-macro>"
        )
        result = render_body(html, "123", {})
        assert '<pre class="code-block"><code>' in result
        assert "print('hello')" in result
        assert "ac:structured-macro" not in result


class TestRenderPanels:
    def test_info_panel(self) -> None:
        html = (
            '<ac:structured-macro ac:name="info">'
            "<ac:rich-text-body><p>Important info</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        result = render_body(html, "123", {})
        assert 'class="panel-info"' in result
        assert "<p>Important info</p>" in result

    def test_warning_panel(self) -> None:
        html = (
            '<ac:structured-macro ac:name="warning">'
            "<ac:rich-text-body><p>Careful!</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        result = render_body(html, "123", {})
        assert 'class="panel-warning"' in result

    def test_note_panel(self) -> None:
        html = (
            '<ac:structured-macro ac:name="note">'
            "<ac:rich-text-body><p>Note this</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        result = render_body(html, "123", {})
        assert 'class="panel-note"' in result

    def test_tip_panel(self) -> None:
        html = (
            '<ac:structured-macro ac:name="tip">'
            "<ac:rich-text-body><p>A tip</p></ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        result = render_body(html, "123", {})
        assert 'class="panel-tip"' in result


class TestRenderStatus:
    def test_status_lozenge(self) -> None:
        html = (
            '<ac:structured-macro ac:name="status">'
            '<ac:parameter ac:name="title">DONE</ac:parameter>'
            '<ac:parameter ac:name="colour">Green</ac:parameter>'
            "</ac:structured-macro>"
        )
        result = render_body(html, "123", {})
        assert 'class="status-lozenge status-green"' in result
        assert "DONE" in result

    def test_status_default_colour(self) -> None:
        html = (
            '<ac:structured-macro ac:name="status">'
            '<ac:parameter ac:name="title">TODO</ac:parameter>'
            "</ac:structured-macro>"
        )
        result = render_body(html, "123", {})
        assert "status-grey" in result


class TestRenderPageLinks:
    def test_internal_link_found(self) -> None:
        html = (
            "<ac:link>"
            '<ri:page ri:content-title="My Page" />'
            "<ac:plain-text-link-body><![CDATA[Click here]]></ac:plain-text-link-body>"
            "</ac:link>"
        )
        title_index = {"my page": "456"}
        result = render_body(html, "123", title_index)
        assert '<a href="/page/456">Click here</a>' in result

    def test_internal_link_not_found(self) -> None:
        html = '<ac:link><ri:page ri:content-title="Missing Page" /></ac:link>'
        result = render_body(html, "123", {})
        assert 'class="broken-link"' in result
        assert "Missing Page" in result

    def test_cross_space_link(self) -> None:
        html = '<ac:link><ri:page ri:space-key="PAAS" ri:content-title="Some Page" /></ac:link>'
        result = render_body(html, "123", {})
        assert 'class="broken-link"' in result
        assert "Some Page" in result

    def test_cross_space_link_with_display_text(self) -> None:
        html = (
            "<ac:link>"
            '<ri:page ri:space-key="ME" ri:content-title="Docker Image" />'
            "<ac:plain-text-link-body>"
            "<![CDATA[instruction]]>"
            "</ac:plain-text-link-body>"
            "</ac:link>"
        )
        result = render_body(html, "123", {})
        assert "instruction" in result


class TestRenderUserMentions:
    def test_user_mention_no_display_name(self) -> None:
        html = '<ac:link><ri:user ri:userkey="abc12345xyz" /></ac:link>'
        result = render_body(html, "123", {})
        assert 'class="user-mention"' in result
        assert "[user: abc12345...]" in result
        assert 'title="Confluence user: abc12345xyz"' in result

    def test_user_mention_with_display_name(self) -> None:
        html = (
            "<ac:link>"
            '<ri:user ri:userkey="abc123" />'
            "<ac:plain-text-link-body>"
            "<![CDATA[John Doe]]>"
            "</ac:plain-text-link-body>"
            "</ac:link>"
        )
        result = render_body(html, "123", {})
        assert 'class="user-mention"' in result
        assert "John Doe" in result


class TestRenderInlineComments:
    def test_inline_comment_unwrapped(self) -> None:
        html = '<ac:inline-comment-marker ac:ref="abc">Some text</ac:inline-comment-marker>'
        result = render_body(html, "123", {})
        assert result == "Some text"
        assert "ac:inline-comment-marker" not in result


class TestRenderTaskLists:
    def test_task_list(self) -> None:
        html = (
            "<ac:task-list>"
            "<ac:task>"
            "<ac:task-id>1</ac:task-id>"
            "<ac:task-status>complete</ac:task-status>"
            "<ac:task-body>Done item</ac:task-body>"
            "</ac:task>"
            "<ac:task>"
            "<ac:task-id>2</ac:task-id>"
            "<ac:task-status>incomplete</ac:task-status>"
            "<ac:task-body>Todo item</ac:task-body>"
            "</ac:task>"
            "</ac:task-list>"
        )
        result = render_body(html, "123", {})
        assert 'class="task-list"' in result
        assert "checked disabled" in result
        assert "Done item" in result
        assert "Todo item" in result


class TestRenderEmoticons:
    def test_smile_emoticon(self) -> None:
        html = '<ac:emoticon ac:name="smile" />'
        result = render_body(html, "123", {})
        assert "\U0001f642" in result

    def test_unknown_emoticon(self) -> None:
        html = '<ac:emoticon ac:name="custom" />'
        result = render_body(html, "123", {})
        assert "[custom]" in result


class TestRenderDrawio:
    def test_drawio_renders_png(self) -> None:
        html = (
            '<ac:structured-macro ac:name="drawio" ac:schema-version="1">'
            '<ac:parameter ac:name="diagramName">my-diagram</ac:parameter>'
            '<ac:parameter ac:name="revision">2</ac:parameter>'
            "</ac:structured-macro>"
        )
        result = render_body(html, "100", {})
        assert '<img src="/attachment/100/my-diagram.png"' in result
        assert 'alt="my-diagram"' in result
        assert "drawio macro" not in result

    def test_drawio_with_spaces_in_name(self) -> None:
        html = (
            '<ac:structured-macro ac:name="drawio" ac:schema-version="1">'
            '<ac:parameter ac:name="diagramName">Bamboo CICD for Python template'
            "</ac:parameter>"
            "</ac:structured-macro>"
        )
        result = render_body(html, "200", {})
        assert '<img src="/attachment/200/Bamboo CICD for Python template.png"' in result

    def test_inc_drawio_uses_page_id_param(self) -> None:
        html = (
            '<ac:structured-macro ac:name="inc-drawio" ac:schema-version="1">'
            '<ac:parameter ac:name="diagramName">my-diagram</ac:parameter>'
            '<ac:parameter ac:name="includedDiagram">1</ac:parameter>'
            '<ac:parameter ac:name="width">987</ac:parameter>'
            '<ac:parameter ac:name="pageId">999</ac:parameter>'
            "</ac:structured-macro>"
        )
        result = render_body(html, "100", {})
        assert '<img src="/attachment/999/my-diagram.png"' in result

    def test_inc_drawio_without_page_id_falls_back(self) -> None:
        html = (
            '<ac:structured-macro ac:name="inc-drawio" ac:schema-version="1">'
            '<ac:parameter ac:name="diagramName">other-diagram</ac:parameter>'
            "</ac:structured-macro>"
        )
        result = render_body(html, "100", {})
        assert '<img src="/attachment/100/other-diagram.png"' in result


class TestRenderPlaceholderMacros:
    def test_toc_macro(self) -> None:
        html = (
            '<ac:structured-macro ac:name="toc">'
            '<ac:parameter ac:name="style">circle</ac:parameter>'
            "</ac:structured-macro>"
        )
        result = render_body(html, "123", {})
        assert "[toc macro]" in result
        assert 'class="macro-placeholder"' in result

    def test_jira_macro(self) -> None:
        html = (
            '<ac:structured-macro ac:name="jira">'
            '<ac:parameter ac:name="key">PROJ-123</ac:parameter>'
            "</ac:structured-macro>"
        )
        result = render_body(html, "123", {})
        assert "[jira macro]" in result


class TestStripRemainingAcRi:
    def test_unknown_macro_shows_placeholder(self) -> None:
        html = (
            '<ac:structured-macro ac:name="fancy-widget" ac:schema-version="1">'
            '<ac:parameter ac:name="key">val</ac:parameter>'
            "</ac:structured-macro>"
        )
        result = render_body(html, "123", {})
        assert "[fancy-widget macro]" in result
        assert 'class="macro-placeholder"' in result
        assert 'title="Unprocessed Confluence macro: fancy-widget"' in result

    def test_strips_unknown_inline_tags(self) -> None:
        html = "<ac:unknown-tag>Keep this text</ac:unknown-tag>"
        result = render_body(html, "123", {})
        assert "Keep this text" in result
        assert "ac:unknown-tag" not in result

    def test_strips_self_closing_ri_tag(self) -> None:
        html = '<ri:something ri:attr="val" />'
        result = render_body(html, "123", {})
        assert "ri:something" not in result


class TestRenderBodyPlainHtml:
    def test_plain_html_passed_through(self) -> None:
        html = "<p>Just a <strong>paragraph</strong></p>"
        result = render_body(html, "123", {})
        assert result == html
