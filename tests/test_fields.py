import json
import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from conftest import resource


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,args,path,method",
    [
        ("get_joomla_fields", {}, "fields/content/articles", "GET"),
        ("get_joomla_field", {"field_id": 3}, "fields/content/articles/3", "GET"),
        ("get_joomla_field_groups", {}, "fields/groups/content/articles", "GET"),
        (
            "get_joomla_field_group",
            {"group_id": 3},
            "fields/groups/content/articles/3",
            "GET",
        ),
        (
            "create_field",
            {"title": "Color", "name": "color", "label": "Color"},
            "fields/content/articles",
            "POST",
        ),
        (
            "create_field_group",
            {"title": "Details"},
            "fields/groups/content/articles",
            "POST",
        ),
        (
            "update_field",
            {"field_id": 3, "expected_title": "Existing", "label": "Color"},
            "fields/content/articles/3",
            "PATCH",
        ),
        (
            "update_field_group",
            {"group_id": 3, "expected_title": "Existing", "description": ""},
            "fields/groups/content/articles/3",
            "PATCH",
        ),
        (
            "delete_field",
            {"field_id": 3, "expected_title": "Existing", "confirm": True},
            "fields/content/articles/3",
            "DELETE",
        ),
        (
            "delete_field_group",
            {"group_id": 3, "expected_title": "Existing", "confirm": True},
            "fields/groups/content/articles/3",
            "DELETE",
        ),
    ],
)
async def test_fields_contract(factory, name, args, path, method):
    calls = []

    def handler(r):
        calls.append(r)
        if r.method in {"PATCH", "DELETE"}:
            return httpx.Response(204)
        data = resource(3, state=-2)
        if name in {"get_joomla_fields", "get_joomla_field_groups"}:
            data = {"data": [data["data"]]}
        return httpx.Response(201 if r.method == "POST" else 200, json=data)

    server, api = factory(handler)
    try:
        assert (await server.call_tool(name, args)).structured_content["ok"]
        assert calls[-1].method == method and calls[-1].url.path.endswith("/" + path)
        if name == "create_field":
            assert json.loads(calls[-1].content)["context"] == "com_content.article"
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_field_values(factory):
    calls = []

    def handler(r):
        calls.append(r)
        if r.url.path.endswith("/fields/content/articles"):
            return httpx.Response(
                200, json={"data": [resource(8, name="color", type="text")["data"]]}
            )
        return (
            httpx.Response(204)
            if r.method == "PATCH"
            else httpx.Response(200, json=resource(3, color="blue"))
        )

    server, api = factory(handler)
    try:
        assert (
            await server.call_tool("get_article_fields", {"article_id": 3})
        ).structured_content["data"]["fields"] == {"color": "blue"}
        await server.call_tool(
            "update_article_fields",
            {"article_id": 3, "expected_title": "Existing", "values": {"color": "red"}},
        )
        assert json.loads(calls[-1].content) == {"color": "red"}
        with pytest.raises(ToolError):
            await server.call_tool(
                "update_article_fields",
                {
                    "article_id": 3,
                    "expected_title": "Existing",
                    "values": {"title": "hacked"},
                },
            )
    finally:
        await api.close()
