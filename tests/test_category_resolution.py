"""Category names never produce guessed article destinations."""

import json
import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from conftest import resource


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ["update_article", "create_article"])
async def test_exact_name_on_later_page(factory, tool):
    writes = []

    def handler(r):
        if r.method != "GET":
            writes.append(r)
            return httpx.Response(201, json=resource(85))
        if r.url.path.endswith("/content/categories"):
            second = r.url.params["page[offset]"] == "100"
            rows = (
                [resource(9, title="Blog")["data"]]
                if second
                else [resource(2, title="Blog archive")["data"]]
            )
            return httpx.Response(
                200, json={"data": rows, "links": {} if second else {"next": "unused"}}
            )
        return httpx.Response(200, json=resource(85))

    server, api = factory(handler)
    args = {"category_name": " blog "}
    args.update(
        {"article_id": 85, "expected_title": "Existing"}
        if tool == "update_article"
        else {"article_text": "Sample"}
    )
    try:
        result = await server.call_tool(tool, args)
        assert not result.is_error
        assert len(writes) == 1
        assert json.loads(writes[0].content)["catid"] == 9
        assert "category_name" not in json.loads(writes[0].content)
    finally:
        await api.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("names", [[], ["Blog archive"], ["Blog", "BLOG"]])
async def test_ambiguous_or_missing_match_never_writes(factory, names):
    calls = []

    def handler(r):
        calls.append(r)
        if r.url.path.endswith("/content/categories"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        resource(i + 9, title=name, parent_id=1)["data"]
                        for i, name in enumerate(names)
                    ]
                },
            )
        return httpx.Response(200, json=resource(85))

    server, api = factory(handler)
    try:
        with pytest.raises(ToolError, match="Ask the user|ask the user") as exc:
            await server.call_tool(
                "update_article",
                {
                    "article_id": 85,
                    "expected_title": "Existing",
                    "category_name": "Blog",
                },
            )
        if len(names) == 2:
            assert '"id": 9' in str(exc.value) and '"id": 10' in str(exc.value)
        assert all(r.method == "GET" for r in calls)
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_id_name_mismatch_never_writes(factory):
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(
            200,
            json=(
                resource(9, title="News")
                if "/categories/" in r.url.path
                else resource(85)
            ),
        )

    server, api = factory(handler)
    try:
        with pytest.raises(ToolError, match="do not match"):
            await server.call_tool(
                "update_article",
                {
                    "article_id": 85,
                    "expected_title": "Existing",
                    "category_id": 9,
                    "category_name": "Blog",
                },
            )
        assert all(r.method == "GET" for r in calls)
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_incomplete_lookup_never_chooses_match(factory):
    calls = []

    def handler(r):
        calls.append(r)
        if r.url.path.endswith("/content/categories"):
            return httpx.Response(
                200,
                json={
                    "data": [resource(9, title="Blog")["data"]],
                    "links": {"next": "unused"},
                },
            )
        return httpx.Response(200, json=resource(85))

    server, api = factory(handler)
    try:
        with pytest.raises(ToolError, match="1,000"):
            await server.call_tool(
                "update_article",
                {
                    "article_id": 85,
                    "expected_title": "Existing",
                    "category_name": "Blog",
                },
            )
        assert len(calls) == 11 and all(r.method == "GET" for r in calls)
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_missing_category_asks_before_creation(factory):
    calls = []
    server, api = factory(lambda r: calls.append(r))
    try:
        with pytest.raises(ToolError, match="ask the user"):
            await server.call_tool("create_article", {"article_text": "Draft"})
        assert not calls
    finally:
        await api.close()
