"""Opt-in, read-only user tools with a strict public attribute allowlist."""

from typing import Any
from mcp.server.mcpserver import MCPServer
from .client import JoomlaClient
from .models import Id, Limit, Offset
from .safety import READ

PUBLIC = {"id", "name", "username", "block"}


def public_user(data: dict) -> dict:
    return {
        "id": data["id"],
        "attributes": {k: v for k, v in data["attributes"].items() if k in PUBLIC},
    }


def register(server: MCPServer, client: JoomlaClient) -> None:
    if not client.settings.enable_users:
        return

    @server.tool(annotations=READ)
    async def get_joomla_users(limit: Limit = 20, offset: Offset = 0) -> dict[str, Any]:
        """List a bounded page of users with ID/name/username/block only. Opt-in read-only capability; sensitive attributes are excluded."""
        result = await client.listing("users", limit, offset)
        result["data"] = [public_user(item) for item in result["data"]]
        return result

    @server.tool(annotations=READ)
    async def get_joomla_user(user_id: Id) -> dict[str, Any]:
        """Read a user by ID. Returns only ID/name/username/block; cannot create users or change permissions."""
        return {
            "ok": True,
            "data": public_user((await client.detail("users", user_id)).public()),
        }
