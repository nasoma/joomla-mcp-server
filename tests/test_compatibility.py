"""Offline SDK/dependency compatibility checks; no live Joomla requests."""

import asyncio
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Import with dummy credentials, regardless of the caller's environment.
with patch.dict(
    os.environ,
    {
        "JOOMLA_BASE_URL": "https://joomla.invalid",
        "BEARER_TOKEN": "test-token-not-a-secret",
    },
):
    import main

ROOT = Path(__file__).resolve().parents[1]
RealClient = httpx.AsyncClient


class CompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_startup_and_discovery(self):
        env = dict(
            os.environ,
            JOOMLA_BASE_URL="https://joomla.invalid",
            BEARER_TOKEN="test-token-not-a-secret",
        )

        async def check():
            async with stdio_client(
                StdioServerParameters(
                    command=sys.executable,
                    args=[str(ROOT / "main.py")],
                    env=env,
                )
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    result = await session.initialize()
                    self.assertEqual(result.server_info.name, "Joomla Articles MCP")
                    tools = await session.list_tools()
                    self.assertEqual(
                        {tool.name for tool in tools.tools},
                        {
                            "get_joomla_articles",
                            "get_joomla_categories",
                            "create_article",
                            "manage_article_state",
                            "move_article_to_trash",
                            "update_article",
                        },
                    )

        await asyncio.wait_for(check(), timeout=20)

    async def invoke(self, name, arguments, responses):
        requests = []

        def respond(request):
            self.assertEqual(request.url.host, "joomla.invalid")
            self.assertEqual(
                request.headers["Authorization"], "Bearer test-token-not-a-secret"
            )
            requests.append(request)
            self.assertTrue(responses, "Unexpected API request")
            status, data = responses.pop(0)
            return httpx.Response(status, json=data)

        def client(*args, **kwargs):
            return RealClient(transport=httpx.MockTransport(respond))

        with patch.object(main.httpx, "AsyncClient", client):
            result = await main.mcp.call_tool(name, arguments)
        self.assertFalse(result.is_error)
        self.assertFalse(responses, "Expected API request did not occur")
        return (
            "\n".join(block.text for block in result.content if hasattr(block, "text")),
            requests,
        )

    async def test_all_tools_success(self):
        categories = {"data": [{"attributes": {"id": 7, "title": "News"}}]}
        article = {"data": {"attributes": {"title": "Existing", "state": 0}}}
        cases = [
            ("get_joomla_articles", {}, [(200, {"data": []})], '"data"', ["GET"]),
            ("get_joomla_categories", {}, [(200, categories)], "News", ["GET"]),
            (
                "create_article",
                {"article_text": "**Hello**", "title": "New", "category_id": 7},
                [(200, categories), (201, {})],
                "Successfully created",
                ["GET", "POST"],
            ),
            (
                "manage_article_state",
                {"article_id": 3, "target_state": 1},
                [(200, article), (204, {})],
                "Successfully updated",
                ["GET", "PATCH"],
            ),
            (
                "move_article_to_trash",
                {"article_id": 3, "expected_title": "Existing"},
                [(200, article), (200, article), (204, {})],
                "trashed",
                ["GET", "GET", "PATCH"],
            ),
            (
                "update_article",
                {"article_id": 3, "introtext": "Intro", "fulltext": "Body"},
                [(200, article), (204, {})],
                "Successfully updated",
                ["GET", "PATCH"],
            ),
        ]
        for name, args, responses, expected, methods in cases:
            with self.subTest(tool=name):
                text, requests = await self.invoke(name, args, responses)
                self.assertIn(expected, text)
                self.assertEqual([r.method for r in requests], methods)
                if name == "create_article":
                    self.assertEqual(
                        json.loads(requests[-1].content)["articletext"],
                        "<p><strong>Hello</strong></p>",
                    )
                elif name == "update_article":
                    self.assertEqual(
                        json.loads(requests[-1].content),
                        {"introtext": "<p>Intro</p>", "fulltext": "<p>Body</p>"},
                    )
                elif name == "move_article_to_trash":
                    self.assertEqual(json.loads(requests[-1].content), {"state": -2})

    async def test_all_tools_api_failure(self):
        cases = [
            ("get_joomla_articles", {}),
            ("get_joomla_categories", {}),
            ("create_article", {"article_text": "Body", "category_id": 7}),
            ("manage_article_state", {"article_id": 3, "target_state": 1}),
            ("move_article_to_trash", {"article_id": 3}),
            ("update_article", {"article_id": 3, "title": "New"}),
        ]
        for name, args in cases:
            with self.subTest(tool=name):
                text, requests = await self.invoke(name, args, [(403, {"errors": []})])
                self.assertIn("HTTP 403", text)
                self.assertEqual([r.method for r in requests], ["GET"])

    async def test_trash_title_mismatch_does_not_write(self):
        text, requests = await self.invoke(
            "move_article_to_trash",
            {
                "article_id": 3,
                "expected_title": "Different",
            },
            [(200, {"data": {"attributes": {"title": "Existing", "state": 0}}})],
        )
        self.assertIn("does not match", text)
        self.assertEqual([r.method for r in requests], ["GET"])

    async def test_html_conversion(self):
        html = main.convert_text_to_html("**Bold** <img src=x onerror=alert(1)>")
        self.assertIn("<strong>Bold</strong>", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("onerror", html)


if __name__ == "__main__":
    unittest.main()
