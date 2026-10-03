"""Smoke-test a supplied stdio command with dummy configuration (no Joomla calls)."""

import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def check():
    command, args = sys.argv[1], sys.argv[2:]
    env = dict(
        os.environ,
        JOOMLA_BASE_URL="https://joomla.invalid",
        BEARER_TOKEN="dummy-test-token",
        JOOMLA_READ_ONLY="true",
        JOOMLA_ENABLE_USERS="false",
    )
    async with stdio_client(
        StdioServerParameters(command=command, args=args, env=env)
    ) as (read, write):
        async with ClientSession(read, write) as session:
            assert (
                await session.initialize()
            ).server_info.name == "Joomla Articles MCP"
            tools = (await session.list_tools()).tools
            assert len(tools) == 47
            assert all(
                t.annotations is not None and t.output_schema is not None for t in tools
            )
            result = await session.call_tool(
                "create_article", {"article_text": "Body", "category_id": 7}
            )
            assert result.is_error and "disabled" in result.content[0].text
            print(
                f"Stdio smoke passed: {len(tools)} tools and read-only error handling."
            )


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(check(), 30))
