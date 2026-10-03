"""Scoped site menu and module tools; no administrator-layout writes."""

from typing import Annotated, Any, Literal
from urllib.parse import urlsplit
from pydantic import Field
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from .client import JoomlaClient
from .models import Id, Limit, Offset, Title, Text, Meta, State, ContentMode
from .content import convert_content
from .safety import READ, WRITE, DESTRUCTIVE, check_identity, valid_state
from .taxonomy import edit_resource, delete_resource

MenuType = Annotated[
    str, Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
]
Position = Annotated[str, Field(max_length=100, pattern=r"^[a-zA-Z0-9_-]*$")]
MENUS = "menus/site"
ITEMS = "menus/site/items"
MODULES = "modules/site"


def validate_link(link: str) -> str:
    parsed = urlsplit(link)
    if (
        any(ord(c) < 32 for c in link)
        or "\\" in link
        or parsed.username
        or parsed.password
    ):
        raise ToolError("Menu link must not contain credentials or control characters.")
    if parsed.scheme:
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise ToolError(
                "Menu links permit HTTP(S) URLs or Joomla index.php component links."
            )
    elif not link.startswith("index.php?option=com_"):
        raise ToolError("Internal menu links must start with index.php?option=com_.")
    return link


def register(server: MCPServer, client: JoomlaClient) -> None:
    @server.tool(annotations=READ)
    async def get_joomla_menus(limit: Limit = 20, offset: Offset = 0) -> dict[str, Any]:
        """List site menus (not administrator menus)."""
        return await client.listing(MENUS, limit, offset)

    @server.tool(annotations=READ)
    async def get_joomla_menu(menu_id: Id) -> dict[str, Any]:
        """Get one site menu by ID."""
        return {"ok": True, "data": (await client.detail(MENUS, menu_id)).public()}

    @server.tool(annotations=WRITE)
    async def create_menu(
        title: Title, menutype: MenuType, description: Meta = ""
    ) -> dict[str, Any]:
        """Create a site menu container. A menu module may be needed to show it on the site."""
        return await client.create(
            MENUS,
            {
                "title": title,
                "menutype": menutype,
                "description": description,
                "client_id": 0,
            },
        )

    @server.tool(annotations=WRITE)
    async def update_menu(
        menu_id: Id,
        expected_title: Title,
        title: Title | None = None,
        description: Meta | None = None,
    ) -> dict[str, Any]:
        """Edit only the site menu title/description; menutype is preserved to avoid orphaning menu items."""
        return await edit_resource(
            client,
            MENUS,
            menu_id,
            expected_title,
            {
                k: v
                for k, v in [("title", title), ("description", description)]
                if v is not None
            },
        )

    @server.tool(annotations=DESTRUCTIVE)
    async def delete_menu(
        menu_id: Id, expected_title: Title, confirm: bool = False
    ) -> dict[str, Any]:
        """Permanently delete a site menu container after title confirmation; may affect contained navigation."""
        return await delete_resource(client, MENUS, menu_id, expected_title, confirm)

    @server.tool(annotations=READ)
    async def get_joomla_menu_items(
        limit: Limit = 20, offset: Offset = 0, menutype: MenuType | None = None
    ) -> dict[str, Any]:
        """List site menu items, optionally filtered by menutype."""
        return await client.listing(
            ITEMS, limit, offset, {"filter[menutype]": menutype} if menutype else None
        )

    @server.tool(annotations=READ)
    async def get_joomla_menu_item(item_id: Id) -> dict[str, Any]:
        """Get one site menu item before editing."""
        return {"ok": True, "data": (await client.detail(ITEMS, item_id)).public()}

    @server.tool(annotations=WRITE)
    async def create_menu_item(
        title: Title,
        menutype: MenuType,
        link: Meta,
        item_type: Literal["url", "component"] = "url",
        component_id: Id | None = None,
        parent_id: Id = 1,
        published: bool = False,
    ) -> dict[str, Any]:
        """Create a draft site menu item. Component links require the installed component_id; external links use type=url."""
        client.require_write()
        validate_link(link)
        if item_type == "component" and (
            component_id is None or not link.startswith("index.php?option=com_")
        ):
            raise ToolError(
                "Component menu items require component_id and a Joomla component link."
            )
        payload = {
            "title": title,
            "menutype": menutype,
            "link": link,
            "type": item_type,
            "parent_id": parent_id,
            "published": 1 if published else 0,
            "language": "*",
            "access": 1,
            "client_id": 0,
        }
        if component_id is not None:
            payload["component_id"] = component_id
        return await client.create(ITEMS, payload)

    @server.tool(annotations=DESTRUCTIVE)
    async def update_menu_item(
        item_id: Id,
        expected_title: Title,
        title: Title | None = None,
        link: Meta | None = None,
        published: State | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Edit site menu item title/link/publication only. Preserves type, parent, menutype and home-page settings."""
        payload = {
            k: v
            for k, v in [
                ("title", title),
                ("link", validate_link(link) if link is not None else None),
                (
                    "published",
                    valid_state(published) if published is not None else None,
                ),
            ]
            if v is not None
        }
        return await edit_resource(
            client, ITEMS, item_id, expected_title, payload, confirm=confirm
        )

    @server.tool(annotations=DESTRUCTIVE)
    async def delete_menu_item(
        item_id: Id, expected_title: Title, confirm: bool = False
    ) -> dict[str, Any]:
        """Permanently delete a trashed site menu item with exact title and confirm=true."""
        return await delete_resource(
            client, ITEMS, item_id, expected_title, confirm, require_trashed=True
        )

    @server.tool(annotations=READ)
    async def get_joomla_modules(
        limit: Limit = 20, offset: Offset = 0
    ) -> dict[str, Any]:
        """List one page of site modules."""
        return await client.listing(MODULES, limit, offset)

    @server.tool(annotations=READ)
    async def get_joomla_module(module_id: Id) -> dict[str, Any]:
        """Read a site module by ID, including its module type."""
        return {"ok": True, "data": (await client.detail(MODULES, module_id)).public()}

    @server.tool(annotations=WRITE)
    async def create_custom_module(
        title: Title,
        content: Text,
        position: Position = "",
        published: bool = False,
        content_mode: ContentMode = "markdown",
    ) -> dict[str, Any]:
        """Create a draft site mod_custom module. Empty position leaves placement for administrator configuration."""
        client.require_write()
        return await client.create(
            MODULES,
            {
                "title": title,
                "content": convert_content(
                    content, content_mode, client.settings.allow_trusted_html
                ),
                "module": "mod_custom",
                "position": position,
                "published": 1 if published else 0,
                "language": "*",
                "access": 1,
                "client_id": 0,
                "showtitle": 1,
            },
        )

    @server.tool(annotations=DESTRUCTIVE)
    async def update_module(
        module_id: Id,
        expected_title: Title,
        title: Title | None = None,
        content: Text | None = None,
        position: Position | None = None,
        published: State | None = None,
        content_mode: ContentMode = "markdown",
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Edit site module title/position/state. Content edits are restricted to mod_custom; arbitrary params and administrator modules are not exposed."""
        client.require_write()
        payload = {
            k: v
            for k, v in [
                ("title", title),
                ("position", position),
                (
                    "published",
                    valid_state(published) if published is not None else None,
                ),
            ]
            if v is not None
        }
        if published == -2:
            from .safety import require_confirmation

            require_confirmation(confirm)
        resource = await client.detail(MODULES, module_id)
        check_identity(resource, expected_title, required=True)
        if content is not None:
            if resource.attributes.get("module") != "mod_custom":
                raise ToolError("Content edits require a mod_custom module.")
            payload["content"] = convert_content(
                content, content_mode, client.settings.allow_trusted_html
            )
        if not payload:
            raise ToolError("Provide at least one field to update.")
        return await client.update(MODULES, resource, payload)

    @server.tool(annotations=DESTRUCTIVE)
    async def delete_module(
        module_id: Id, expected_title: Title, confirm: bool = False
    ) -> dict[str, Any]:
        """Permanently delete an already trashed site module with exact title and confirm=true."""
        return await delete_resource(
            client, MODULES, module_id, expected_title, confirm, require_trashed=True
        )
