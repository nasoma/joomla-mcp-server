"""Article custom fields and field definition/group management."""

from typing import Annotated, Any, Literal
import json
import re
import bleach
from pydantic import Field
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from .client import JoomlaClient
from .models import Id, Limit, Offset, Title, Meta, Text, State
from .safety import READ, WRITE, DESTRUCTIVE, check_identity, valid_state
from .taxonomy import edit_resource, delete_resource

FIELDS = "fields/content/articles"
GROUPS = "fields/groups/content/articles"
FieldName = Annotated[
    str, Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9-]*$")
]
FieldType = Literal["text", "textarea", "integer"]
RESERVED = {
    "id",
    "title",
    "alias",
    "state",
    "introtext",
    "fulltext",
    "articletext",
    "catid",
    "tags",
    "images",
    "metadesc",
    "metakey",
    "language",
    "access",
    "featured",
    "com_fields",
    "modified",
    "created",
}


def field_name(name: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", name) or name in RESERVED:
        raise ToolError(
            "Field name is invalid or conflicts with a core article attribute."
        )
    return name


async def definitions(client: JoomlaClient) -> list[dict]:
    result = []
    for offset in range(0, 1000, 100):
        page = await client.listing(FIELDS, 100, offset)
        result.extend(page["data"])
        if not page["pagination"]["has_next"]:
            return result
    raise ToolError(
        "Too many field definitions; cannot safely validate article fields."
    )


def register(server: MCPServer, client: JoomlaClient) -> None:
    @server.tool(annotations=READ)
    async def get_joomla_fields(
        limit: Limit = 20, offset: Offset = 0
    ) -> dict[str, Any]:
        """List article field definitions. Types/plugins determine supported field values."""
        return await client.listing(FIELDS, limit, offset)

    @server.tool(annotations=READ)
    async def get_joomla_field(field_id: Id) -> dict[str, Any]:
        """Get an article field definition by ID."""
        return {"ok": True, "data": (await client.detail(FIELDS, field_id)).public()}

    @server.tool(annotations=WRITE)
    async def create_field(
        title: Title,
        name: FieldName,
        label: Title,
        field_type: FieldType = "text",
        group_id: Id | None = None,
        default_value: Meta = "",
    ) -> dict[str, Any]:
        """Create an unpublished text, textarea or integer article field. Other field types require plugin-specific configuration."""
        client.require_write()
        payload = {
            "title": title,
            "name": field_name(name),
            "label": label,
            "type": field_type,
            "context": "com_content.article",
            "state": 0,
            "language": "*",
            "default_value": bleach.clean(default_value, tags=[], strip=True),
            "access": 1,
        }
        if group_id is not None:
            payload["group_id"] = group_id
        return await client.create(FIELDS, payload)

    @server.tool(annotations=DESTRUCTIVE)
    async def update_field(
        field_id: Id,
        expected_title: Title,
        title: Title | None = None,
        label: Title | None = None,
        default_value: Meta | None = None,
        state: State | None = None,
        group_id: Id | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Edit safe field definition properties. Field name/type stay unchanged to protect stored values."""
        payload = {
            k: v
            for k, v in [
                ("title", title),
                ("label", label),
                ("state", valid_state(state) if state is not None else None),
                ("group_id", group_id),
            ]
            if v is not None
        }
        if default_value is not None:
            payload["default_value"] = bleach.clean(default_value, tags=[], strip=True)
        return await edit_resource(
            client, FIELDS, field_id, expected_title, payload, confirm=confirm
        )

    @server.tool(annotations=DESTRUCTIVE)
    async def delete_field(
        field_id: Id, expected_title: Title, confirm: bool = False
    ) -> dict[str, Any]:
        """Permanently delete a trashed article field definition; stored field values may be lost."""
        return await delete_resource(
            client, FIELDS, field_id, expected_title, confirm, require_trashed=True
        )

    @server.tool(annotations=READ)
    async def get_joomla_field_groups(
        limit: Limit = 20, offset: Offset = 0
    ) -> dict[str, Any]:
        """List article field groups."""
        return await client.listing(GROUPS, limit, offset)

    @server.tool(annotations=READ)
    async def get_joomla_field_group(group_id: Id) -> dict[str, Any]:
        """Read an article field group by ID."""
        return {"ok": True, "data": (await client.detail(GROUPS, group_id)).public()}

    @server.tool(annotations=WRITE)
    async def create_field_group(
        title: Title, description: Meta = ""
    ) -> dict[str, Any]:
        """Create an unpublished article field group."""
        client.require_write()
        return await client.create(
            GROUPS,
            {
                "title": title,
                "description": bleach.clean(description, tags=[], strip=True),
                "context": "com_content.article",
                "state": 0,
                "language": "*",
                "access": 1,
            },
        )

    @server.tool(annotations=DESTRUCTIVE)
    async def update_field_group(
        group_id: Id,
        expected_title: Title,
        title: Title | None = None,
        description: Meta | None = None,
        state: State | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Update a field group; state=-2 requires destructive confirmation."""
        payload = {
            k: v
            for k, v in [
                ("title", title),
                ("state", valid_state(state) if state is not None else None),
            ]
            if v is not None
        }
        if description is not None:
            payload["description"] = bleach.clean(description, tags=[], strip=True)
        return await edit_resource(
            client, GROUPS, group_id, expected_title, payload, confirm=confirm
        )

    @server.tool(annotations=DESTRUCTIVE)
    async def delete_field_group(
        group_id: Id, expected_title: Title, confirm: bool = False
    ) -> dict[str, Any]:
        """Permanently delete an already trashed article field group after exact title confirmation."""
        return await delete_resource(
            client, GROUPS, group_id, expected_title, confirm, require_trashed=True
        )

    @server.tool(annotations=READ)
    async def get_article_fields(article_id: Id) -> dict[str, Any]:
        """Read custom field values exposed by Joomla for this article, matched against field definitions."""
        article = await client.detail("content/articles", article_id)
        names = [item["attributes"].get("name") for item in await definitions(client)]
        return {
            "ok": True,
            "data": {
                "id": article.id,
                "fields": {
                    name: article.attributes.get(name)
                    for name in names
                    if isinstance(name, str) and name not in RESERVED
                },
            },
        }

    @server.tool(annotations=WRITE)
    async def update_article_fields(
        article_id: Id,
        expected_title: Title,
        values: Annotated[dict[str, str | int], Field(min_length=1, max_length=50)],
        expected_modified: Meta | None = None,
    ) -> dict[str, Any]:
        """Update named text/textarea/integer article fields. Empty string clears text. Unknown/unsupported field names and types are rejected."""
        client.require_write()
        if len(json.dumps(values)) > 100_000:
            raise ToolError("Field values exceed size limit.")
        resource = await client.detail("content/articles", article_id)
        check_identity(resource, expected_title, expected_modified, required=True)
        known = {
            item["attributes"].get("name"): item["attributes"]
            for item in await definitions(client)
        }
        payload = {}
        for name, value in values.items():
            field_name(name)
            field = known.get(name)
            if not field or field.get("type") not in {"text", "textarea", "integer"}:
                raise ToolError(
                    "Unknown field or unsupported field type; inspect field definitions."
                )
            if field["type"] == "integer":
                if type(value) is not int:
                    raise ToolError("Integer fields require integer values.")
                payload[name] = value
            else:
                if not isinstance(value, str):
                    raise ToolError("Text fields require string values.")
                payload[name] = bleach.clean(value, tags=[], strip=True)
        return await client.update("content/articles", resource, payload)
