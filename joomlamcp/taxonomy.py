"""Content category and tag CRUD with explicit destructive confirmation."""

from typing import Any
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from .client import JoomlaClient
from .models import Id, Limit, Offset, Title, Text, Meta, State, ContentMode
from .content import convert_content
from .safety import (
    READ,
    WRITE,
    DESTRUCTIVE,
    check_identity,
    valid_state,
    require_confirmation,
)


async def edit_resource(
    client: JoomlaClient,
    path: str,
    resource_id: int,
    expected_title: str,
    payload: dict,
    *,
    confirm: bool = False,
    title_key: str = "title",
) -> dict:
    client.require_write()
    if not payload:
        raise ToolError("Provide at least one field to update.")
    if payload.get("published", payload.get("state")) == -2:
        require_confirmation(confirm)
    resource = await client.detail(path, resource_id)
    check_identity(resource, expected_title, required=True, title_key=title_key)
    return await client.update(path, resource, payload)


async def delete_resource(
    client: JoomlaClient,
    path: str,
    resource_id: int,
    expected_title: str,
    confirm: bool,
    *,
    title_key: str = "title",
    require_trashed: bool = False,
) -> dict:
    client.require_write()
    require_confirmation(confirm)
    resource = await client.detail(path, resource_id)
    check_identity(resource, expected_title, required=True, title_key=title_key)
    if (
        require_trashed
        and str(resource.attributes.get("published", resource.attributes.get("state")))
        != "-2"
    ):
        raise ToolError(
            "Trash this resource first via its update tool; permanent deletion requires trashed state."
        )
    return await client.delete(path, resource)


def register(server: MCPServer, client: JoomlaClient) -> None:
    @server.tool(annotations=READ)
    async def get_joomla_category(category_id: Id) -> dict[str, Any]:
        """Read a content category by ID before editing or deleting."""
        return {
            "ok": True,
            "data": (await client.detail("content/categories", category_id)).public(),
        }

    @server.tool(annotations=WRITE)
    async def create_category(
        title: Title,
        parent_id: Id = 1,
        description: Text = "",
        published: bool = False,
        content_mode: ContentMode = "markdown",
    ) -> dict[str, Any]:
        """Create an unpublished content category; parent_id=1 is Joomla's category root."""
        client.require_write()
        return await client.create(
            "content/categories",
            {
                "title": title,
                "parent_id": parent_id,
                "extension": "com_content",
                "description": convert_content(
                    description, content_mode, client.settings.allow_trusted_html
                ),
                "published": 1 if published else 0,
                "language": "*",
            },
        )

    @server.tool(annotations=DESTRUCTIVE)
    async def update_category(
        category_id: Id,
        expected_title: Title,
        title: Title | None = None,
        description: Text | None = None,
        parent_id: Id | None = None,
        published: State | None = None,
        content_mode: ContentMode = "markdown",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Edit supplied category fields. Published uses 1/0/2/-2; trash (-2) needs confirm=true."""
        payload = {
            k: v
            for k, v in [
                ("title", title),
                ("parent_id", parent_id),
                (
                    "published",
                    valid_state(published) if published is not None else None,
                ),
            ]
            if v is not None
        }
        if description is not None:
            payload["description"] = convert_content(
                description, content_mode, client.settings.allow_trusted_html
            )
        return await edit_resource(
            client,
            "content/categories",
            category_id,
            expected_title,
            payload,
            confirm=confirm,
        )

    @server.tool(annotations=DESTRUCTIVE)
    async def delete_category(
        category_id: Id, expected_title: Title, confirm: bool = False
    ) -> dict[str, Any]:
        """Permanently delete an already trashed category. Requires exact expected_title and confirm=true; Joomla may reject nonempty categories."""
        return await delete_resource(
            client,
            "content/categories",
            category_id,
            expected_title,
            confirm,
            require_trashed=True,
        )

    @server.tool(annotations=READ)
    async def get_joomla_tags(limit: Limit = 20, offset: Offset = 0) -> dict[str, Any]:
        """List one bounded page of tags."""
        return await client.listing("tags", limit, offset)

    @server.tool(annotations=READ)
    async def get_joomla_tag(tag_id: Id) -> dict[str, Any]:
        """Read a tag by ID before editing or deleting."""
        return {"ok": True, "data": (await client.detail("tags", tag_id)).public()}

    @server.tool(annotations=WRITE)
    async def create_tag(
        title: Title,
        description: Text = "",
        parent_id: Id = 1,
        published: bool = False,
        content_mode: ContentMode = "markdown",
    ) -> dict[str, Any]:
        """Create an unpublished tag; use update_article(tags=[IDs]) to assign tags to an article."""
        client.require_write()
        return await client.create(
            "tags",
            {
                "title": title,
                "description": convert_content(
                    description, content_mode, client.settings.allow_trusted_html
                ),
                "parent_id": parent_id,
                "published": 1 if published else 0,
                "language": "*",
            },
        )

    @server.tool(annotations=DESTRUCTIVE)
    async def update_tag(
        tag_id: Id,
        expected_title: Title,
        title: Title | None = None,
        description: Text | None = None,
        published: State | None = None,
        content_mode: ContentMode = "markdown",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Update supplied tag fields. Trashing via published=-2 requires confirm=true."""
        payload = {
            k: v
            for k, v in [
                ("title", title),
                (
                    "published",
                    valid_state(published) if published is not None else None,
                ),
            ]
            if v is not None
        }
        if description is not None:
            payload["description"] = convert_content(
                description, content_mode, client.settings.allow_trusted_html
            )
        return await edit_resource(
            client, "tags", tag_id, expected_title, payload, confirm=confirm
        )

    @server.tool(annotations=DESTRUCTIVE)
    async def delete_tag(
        tag_id: Id, expected_title: Title, confirm: bool = False
    ) -> dict[str, Any]:
        """Permanently delete an already trashed tag with exact expected_title and confirm=true."""
        return await delete_resource(
            client, "tags", tag_id, expected_title, confirm, require_trashed=True
        )
