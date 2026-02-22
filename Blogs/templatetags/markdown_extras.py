from django import template
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
import markdown

register = template.Library()

# fenced_code, tables, sane_lists. smarty (em-dash, ellipsis) added if available.
def _get_md_extensions():
    base = ["fenced_code", "tables", "sane_lists"]
    try:
        markdown.markdown("test", extensions=base + ["smarty"])
        return base + ["smarty"]
    except Exception:
        return base


_MARKDOWN_EXTENSIONS = _get_md_extensions()


@register.filter
def markdownify(text):
    """Render Markdown to HTML. Handles None/empty. Output is safe for template |safe."""
    if text is None:
        return mark_safe("")
    text = str(text).strip()
    if not text:
        return mark_safe("")
    try:
        html = markdown.markdown(text, extensions=_MARKDOWN_EXTENSIONS)
        return mark_safe(html)
    except Exception:
        from django.utils.html import escape
        return mark_safe("<p>" + escape(text) + "</p>")


@register.filter
def markdown_to_plain(text):
    """Convert markdown to plain text for previews (strips #, **, etc.)."""
    if not text:
        return ""
    try:
        html = markdown.markdown(
            str(text),
            extensions=_MARKDOWN_EXTENSIONS,
        )
        plain = strip_tags(html).replace("\n", " ").strip()
        while "  " in plain:
            plain = plain.replace("  ", " ")
        return plain
    except Exception:
        return strip_tags(str(text))[:500]