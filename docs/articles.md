# Article behavior and migration

Existing six tool names remain; `get_joomla_article` adds an ID lookup. Results are now
structured dictionaries with `ok`, normalized `data` and (for lists) `pagination`.
Failures raise MCP ToolErrors and become `is_error=true` over stdio, instead of success strings.
Lists default to 20 rows, maximum 100; repeat with `next_offset`. Article lists omit large
content attributes by default; set `include_content=true` or fetch an individual article.
Supported article filters are search, category_id, state and tag_id.

Creation requires a category ID validated with its detail endpoint and defaults to an
unpublished draft. Set `published=true` deliberately to publish. Inferred titles use source
text without markup; aliases default to Joomla generation. Success returns the new ID.

For updates, omitted/null fields are unchanged; empty text/meta strings clear a field.
`introtext` and `fulltext` can be changed independently using PATCH. Neither is combined
into `articletext`. A title change keeps its alias unless a new alias is supplied.
Supply the exact `expected_title` read from the detail tool for every existing article write.
Trash additionally requires `confirm=true` and only changes state to -2. There is no permanent
article delete. Trash uses one identity GET, not two. `expected_modified` rejects a stale
snapshot; If-Match is sent when Joomla supplies an ETag. Without server ETag enforcement,
identity/timestamp checks cannot provide atomic conflict protection.

`content_mode=markdown` converts Markdown and sanitizes it. `html` sanitizes supplied HTML;
`trusted_html` preserves bytes only when JOOMLA_ALLOW_TRUSTED_HTML=true. Legacy
`convert_plain_text=false` selects sanitized HTML, not a sanitization bypass. Allowed tags
include paragraphs, headings, lists, links, images, code and tables; styles and event handlers
are removed, and URL protocols are restricted. Joomla's own filters still apply. Set trusted
mode only for an authorized source whose inline styles/markup must be preserved.

Run `uv run pytest tests/test_articles.py tests/test_compatibility.py` for offline checks.
