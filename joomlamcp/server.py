"""Application factory and stdio entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import logging
import sys
from mcp.server.mcpserver import MCPServer
from .config import Settings
from .client import JoomlaClient
from . import articles, taxonomy, fields, layout, media, users


def create_server(settings: Settings, client: JoomlaClient | None = None) -> MCPServer:
    api = client or JoomlaClient(settings)

    @asynccontextmanager
    async def lifespan(server: MCPServer) -> AsyncIterator[JoomlaClient]:
        try:
            yield api
        finally:
            await api.close()

    server = MCPServer("Joomla Articles MCP", lifespan=lifespan)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    articles.register(server, api)
    taxonomy.register(server, api)
    fields.register(server, api)
    layout.register(server, api)
    media.register(server, api)
    users.register(server, api)
    return server


def main() -> None:
    try:
        settings = Settings.from_env()
    except ValueError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        raise SystemExit(2) from None
    create_server(settings).run(transport="stdio")
