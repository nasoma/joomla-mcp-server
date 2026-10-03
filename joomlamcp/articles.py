"""Article tools; omitted fields stay unchanged, empty strings clear content."""

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
    ) -> dict[str, Any]:
        """Create an article draft by default. Specify category_id from categories; returns the new resource ID. Raw HTML is sanitized unless trusted_html is explicitly enabled."""
        client.require_write()
        if category_id is None:
            raise ToolError(
                "category_id is required; use get_joomla_categories to select one."
            )
        await client.detail(CATEGORIES, category_id)
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
        """Set state: 1 published, 0 draft, 2 archived, -2 trash. Exact expected_title is required; trash additionally requires confirm=true."""
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
    ) -> dict[str, Any]:
        """Update supplied fields only; empty strings clear text/meta. Intro and full text can be edited independently. Title changes preserve alias unless explicitly supplied. Read first and supply exact expected_title."""
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
        if not payload:
            raise ToolError("Provide at least one field to update.")
        resource = await client.detail(ARTICLES, article_id)
        check_identity(resource, expected_title, expected_modified, required=True)
        if category_id is not None:
            await client.detail(CATEGORIES, category_id)
        return await client.update(ARTICLES, resource, payload)
