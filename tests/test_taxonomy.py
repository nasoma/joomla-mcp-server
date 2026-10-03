import httpx
import json
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from conftest import resource


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,args,path,method",
    [
        ("get_joomla_category", {"category_id": 3}, "content/categories/3", "GET"),
        ("get_joomla_tag", {"tag_id": 3}, "tags/3", "GET"),
        ("get_joomla_tags", {}, "tags", "GET"),
        ("create_category", {"title": "News"}, "content/categories", "POST"),
        ("create_tag", {"title": "News"}, "tags", "POST"),
        (
            "update_category",
            {"category_id": 3, "expected_title": "Existing", "description": ""},
            "content/categories/3",
            "PATCH",
        ),
        (
            "update_tag",
            {"tag_id": 3, "expected_title": "Existing", "description": ""},
            "tags/3",
            "PATCH",
        ),
        (
            "delete_category",
            {"category_id": 3, "expected_title": "Existing", "confirm": True},
            "content/categories/3",
            "DELETE",
        ),
        (
            "delete_tag",
            {"tag_id": 3, "expected_title": "Existing", "confirm": True},
            "tags/3",
            "DELETE",
        ),
    ],
)
async def test_taxonomy_contract(factory, name, args, path, method):
    calls = []

    def handler(r):
        calls.append(r)
        if r.method in {"PATCH", "DELETE"}:
            return httpx.Response(204)
        data = resource(3, published=-2)
        if name == "get_joomla_tags":
            data = {"data": [data["data"]]}
        return httpx.Response(201 if r.method == "POST" else 200, json=data)

    server, api = factory(handler)
    try:
        result = await server.call_tool(name, args)
        assert result.structured_content["ok"]
        assert calls[-1].url.path.endswith("/" + path) and calls[-1].method == method
        if method == "POST":
            assert json.loads(calls[-1].content)["published"] == 0
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_delete_must_be_trashed(factory):
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(200, json=resource(3, published=1))

    server, api = factory(handler)
    try:
        with pytest.raises(ToolError):
            await server.call_tool(
                "delete_category",
                {"category_id": 3, "expected_title": "Existing", "confirm": True},
            )
        assert [r.method for r in calls] == ["GET"]
    finally:
        await api.close()
