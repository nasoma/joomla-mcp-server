"""Content modes: safe Markdown/HTML by default, explicit trusted HTML."""

import re
import unicodedata
from html import unescape
from html.parser import HTMLParser

import bleach
import markdown
from mcp.server.mcpserver.exceptions import ToolError

TAGS = [
    "p",
    "br",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "a",
    "img",
    "blockquote",
    "pre",
    "code",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "hr",
]
ATTRS = {
    "a": ["href", "title"],
    "img": ["src", "alt", "title", "width", "height"],
    "th": ["scope"],
    "hr": ["id"],
}


def convert_content(text: str, mode: str, allow_trusted: bool) -> str:
    if mode == "trusted_html":
        if not allow_trusted:
            raise ToolError("Trusted HTML requires JOOMLA_ALLOW_TRUSTED_HTML=true.")
        return text
    html = (
        markdown.markdown(text, extensions=["tables", "fenced_code"])
        if mode == "markdown"
        else text
    )
    return bleach.clean(
        html,
        tags=TAGS,
        attributes=ATTRS,
        protocols=["http", "https", "mailto"],
        strip=True,
    )


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def infer_title(source: str) -> str:
    parser = PlainText()
    parser.feed(markdown.markdown(source))
    title = re.sub(r"\s+", " ", unescape(" ".join(parser.parts))).strip()[:80]
    if not title:
        raise ToolError(
            "Provide a nonblank title; it cannot be inferred from empty content."
        )
    return title


def generate_alias(title: str) -> str:
    """Unicode-preserving optional helper; default creation delegates aliases to Joomla."""
    value = unicodedata.normalize("NFKC", title).casefold()
    return re.sub(r"[-\s]+", "-", re.sub(r"[^\w\s-]", "", value)).strip("-_")
