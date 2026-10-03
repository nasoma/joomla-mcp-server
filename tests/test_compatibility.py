"""A real MCP stdio session without live Joomla requests."""

import asyncio
import os
from pathlib import Path
import sys
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_stdio_startup_and_errors():
    env = dict(
        os.environ,
        JOOMLA_BASE_URL="https://joomla.invalid",
        BEARER_TOKEN="dummy-test-token",
        JOOMLA_READ_ONLY="true",
    )

    async def check():
        async with stdio_client(
            StdioServerParameters(
                command=sys.executable,
                args=[str(Path(__file__).resolve().parents[1] / "main.py")],
                env=env,
            )
        ) as (read, write):
            async with ClientSession(read, write) as session:
                assert (
                    await session.initialize()
                ).server_info.name == "Joomla Articles MCP"
                tools = (await session.list_tools()).tools
                assert {t.name for t in tools} >= {
                    "get_joomla_articles",
                    "get_joomla_article",
                    "create_article",
                    "move_article_to_trash",
                    "update_article",
                    "manage_article_state",
                    "get_joomla_categories",
                }
                result = await session.call_tool(
                    "create_article", {"article_text": "Body", "category_id": 7}
                )
                assert result.is_error
                assert "disabled" in result.content[0].text

    await asyncio.wait_for(check(), 20)
