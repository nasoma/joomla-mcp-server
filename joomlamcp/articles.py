"""Article tools; omitted fields stay unchanged, empty strings clear content."""

import json
from typing import Annotated, Any
from pydantic import Field
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from .client import JoomlaClient
from .models import Id, Limit, Offset, Title, Text, Meta, State, ContentMode
from .content import convert_content, infer_title
from .safety import (
    READ,
    WRITE,
    DESTRUCTIVE,
    check_identity,
    valid_state,
    require_confirmation,
)

ARTICLES = "content/articles"
CATEGORIES = "content/categories"
Tags = Annotated[list[Id], Field(max_length=100)]
Alias = Annotated[str, Field(min_length=1, max_length=255, pattern=r"^[\w-]+$")]


async def resolve_category(
    client: JoomlaClient, category_id: int | None, category_name: str | None
) -> int:
    """Require an ID or an unambiguous exact name; never guess a destination."""
    if category_id is not None:
        category = await client.detail(CATEGORIES, category_id)
        if (
            category_name is not None
            and str(category.attributes.get("title", "")).strip().casefold()
            != category_name.strip().casefold()
        ):
            raise ToolError(
                "category_id and category_name do not match. Ask the user which category ID to use before proceeding."
            )
        return category_id
    if category_name is None:
        raise ToolError(
            "A category is required. Use get_joomla_categories, then ask the user which category ID to use before proceeding."
        )
    matches = {}
    offset = 0
    for _ in range(10):
        page = await client.listing(CATEGORIES, 100, offset)
        for category in page["data"]:
            if (
                str(category["attributes"].get("title", "")).strip().casefold()
                == category_name.strip().casefold()
            ):
                matches[category["id"]] = category
        if not page["pagination"]["has_next"]:
            break
        offset = page["pagination"]["next_offset"]
    else:
        raise ToolError(
            "Category lookup exceeded 1,000 categories. Ask the user for the exact category ID before proceeding."
        )
    if len(matches) == 1:
        return int(next(iter(matches)))
    if matches:
        choices = [
            {
                "id": int(item["id"]),
                "title": item["attributes"].get("title"),
                "parent_id": item["attributes"].get("parent_id"),
            }
            for item in matches.values()
        ]
        raise ToolError(
            f"Category name is ambiguous. Ask the user which category ID to use before proceeding. Matches: {json.dumps(choices, ensure_ascii=False)}"
        )
    raise ToolError(
        "No exact category-name match was found. Use get_joomla_categories and ask the user which category ID to use before proceeding."
    )


def register(server: MCPServer, client: JoomlaClient) -> None:
    @server.tool(annotations=READ)
    async def get_joomla_articles(
        limit: Limit = 20,
        offset: Offset = 0,
        search: Meta | None = None,
        category_id: Id | None = None,
        state: State | None = None,
        tag_id: Id | None = None,
        include_content: bool = False,
    ) -> dict[str, Any]:
        """Retrieve one bounded page of articles. Use next_offset for subsequent pages; lookup IDs before writing."""
        filters = {}
        for key, value in [
            ("search", search),
            ("category", category_id),
            ("state", state),
            ("tag", tag_id),
        ]:
            if value is not None:
                filters[f"filter[{key}]"] = (
                    valid_state(value) if key == "state" else value
                )
        result = await client.listing(ARTICLES, limit, offset, filters)
        if not include_content:
            for item in result["data"]:
                item["attributes"] = {
                    k: v
                    for k, v in item["attributes"].items()
                    if k
                    in {
                        "id",
                        "title",
                        "alias",
                        "state",
                        "category",
                        "language",
                        "modified",
                        "created",
                        "featured",
                    }
                }
        return result

    @server.tool(annotations=READ)
    async def get_joomla_article(article_id: Id) -> dict[str, Any]:
        """Get article details by ID, including title, modified timestamp, fields and available ETag."""
        return {
            "ok": True,
            "data": (await client.detail(ARTICLES, article_id)).public(),
        }

    @server.tool(annotations=READ)
    async def get_joomla_categories(
        limit: Limit = 20, offset: Offset = 0, search: Meta | None = None
    ) -> dict[str, Any]:
        """List one page of content categories; follow next_offset to see more."""
        return await client.listing(
            CATEGORIES,
            limit,
            offset,
            {"filter[search]": search} if search is not None else None,
        )

    @server.tool(annotations=WRITE)
    async def create_article(
        article_text: Text,
        title: Title | None = None,
        category_id: Id | None = None,
        convert_plain_text: bool = True,
        published: bool = False,
        content_mode: ContentMode | None = None,
        alias: Alias | None = None,
        tags: Tags | None = None,
        category_name: Title | None = None,
    ) -> dict[str, Any]:
        """Create a draft by default. Accept category_id or an exact category_name (e.g. Blog). If missing or ambiguous, ask the user to choose a category ID before retrying; never invent an ID. published=true publishes at creation. Raw HTML is sanitized unless trusted_html is explicitly enabled."""
        client.require_write()
        category_id = await resolve_category(client, category_id, category_name)
        payload = {
            "title": title or infer_title(article_text),
            "articletext": convert_content(
                article_text,
                content_mode or ("markdown" if convert_plain_text else "html"),
                client.settings.allow_trusted_html,
            ),
            "catid": category_id,
            "language": "*",
            "state": 1 if published else 0,
        }
        if alias is not None:
            payload["alias"] = alias
        if tags is not None:
            payload["tags"] = tags
        return await client.create(ARTICLES, payload)

    @server.tool(annotations=DESTRUCTIVE)
    async def manage_article_state(
        article_id: Id,
        target_state: State,
        expected_title: Title | None = None,
        expected_modified: Meta | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Set state: 1 published, 0 draft, 2 archived, -2 trash. Publishing keeps the current category; use update_article to move categories first when requested. Exact expected_title is required; trash additionally requires confirm=true."""
        client.require_write()
        valid_state(target_state)
        if target_state == -2:
            require_confirmation(confirm)
        resource = await client.detail(ARTICLES, article_id)
        check_identity(resource, expected_title, expected_modified, required=True)
        state = resource.attributes.get("state")
        if (
            state is not None
            and type(state) in {str, int}
            and str(state) == str(target_state)
        ):
            return {"ok": True, "data": {"id": resource.id}, "changed": False}
        return await client.update(ARTICLES, resource, {"state": target_state})

    @server.tool(annotations=DESTRUCTIVE)
    async def move_article_to_trash(
        article_id: Id,
        expected_title: Title | None = None,
        confirm: bool = False,
        expected_modified: Meta | None = None,
    ) -> dict[str, Any]:
        """Recoverably trash an article. First read it, then supply exact expected_title and confirm=true. Never permanently deletes."""
        return await manage_article_state(
            article_id, -2, expected_title, expected_modified, confirm
        )

    @server.tool(annotations=WRITE)
    async def update_article(
        article_id: Id,
        title: Title | None = None,
        introtext: Text | None = None,
        fulltext: Text | None = None,
        metadesc: Meta | None = None,
        convert_plain_text: bool = True,
        content_mode: ContentMode | None = None,
        alias: Alias | None = None,
        category_id: Id | None = None,
        tags: Tags | None = None,
        expected_title: Title | None = None,
        expected_modified: Meta | None = None,
        category_name: Title | None = None,
    ) -> dict[str, Any]:
        """Update supplied fields only. To move an article, supply category_id or exact category_name (e.g. Blog). Missing/ambiguous name matches require asking the user to choose a category ID before retrying; never guess. Empty strings clear text/meta. Intro and full text can be edited independently. Read first and supply exact expected_title."""
        client.require_write()
        payload = {
            key: value
            for key, value in [
                ("title", title),
                ("metadesc", metadesc),
                ("alias", alias),
                ("catid", category_id),
                ("tags", tags),
            ]
            if value is not None
        }
        mode = content_mode or ("markdown" if convert_plain_text else "html")
        for key, value in [("introtext", introtext), ("fulltext", fulltext)]:
            if value is not None:
                payload[key] = convert_content(
                    value, mode, client.settings.allow_trusted_html
                )
        if not payload and category_name is None:
            raise ToolError(
                "Provide at least one field to update. For a category move, ask the user for a category name or ID before proceeding."
            )
        resource = await client.detail(ARTICLES, article_id)
        check_identity(resource, expected_title, expected_modified, required=True)
        if category_id is not None or category_name is not None:
            payload["catid"] = await resolve_category(
                client, category_id, category_name
            )
        return await client.update(ARTICLES, resource, payload)
