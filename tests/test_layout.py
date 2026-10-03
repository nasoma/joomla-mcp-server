import httpx
import json
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from conftest import resource


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,args,path,method",
    [
        ("get_joomla_menus", {}, "menus/site", "GET"),
        ("get_joomla_menu", {"menu_id": 3}, "menus/site/3", "GET"),
        (
            "create_menu",
            {"title": "Menu", "menutype": "new-menu"},
            "menus/site",
            "POST",
        ),
        (
            "update_menu",
            {"menu_id": 3, "expected_title": "Existing", "title": "New"},
            "menus/site/3",
            "PATCH",
        ),
        (
            "delete_menu",
            {"menu_id": 3, "expected_title": "Existing", "confirm": True},
            "menus/site/3",
            "DELETE",
        ),
        ("get_joomla_menu_items", {"menutype": "mainmenu"}, "menus/site/items", "GET"),
        ("get_joomla_menu_item", {"item_id": 3}, "menus/site/items/3", "GET"),
        (
            "create_menu_item",
            {"title": "Link", "menutype": "mainmenu", "link": "https://example.com"},
            "menus/site/items",
            "POST",
        ),
        (
            "update_menu_item",
            {"item_id": 3, "expected_title": "Existing", "title": "New"},
            "menus/site/items/3",
            "PATCH",
        ),
        (
            "delete_menu_item",
            {"item_id": 3, "expected_title": "Existing", "confirm": True},
            "menus/site/items/3",
            "DELETE",
        ),
        ("get_joomla_modules", {}, "modules/site", "GET"),
        ("get_joomla_module", {"module_id": 3}, "modules/site/3", "GET"),
        (
            "create_custom_module",
            {"title": "Custom", "content": "Hello"},
            "modules/site",
            "POST",
        ),
        (
            "update_module",
            {"module_id": 3, "expected_title": "Existing", "content": "New"},
            "modules/site/3",
            "PATCH",
        ),
        (
            "delete_module",
            {"module_id": 3, "expected_title": "Existing", "confirm": True},
            "modules/site/3",
            "DELETE",
        ),
    ],
)
async def test_layout_contract(factory, name, args, path, method):
    calls = []

    def handler(r):
        calls.append(r)
        if r.method in {"PATCH", "DELETE"}:
            return httpx.Response(204)
        data = resource(3, published=-2, module="mod_custom")
        if name in {"get_joomla_menus", "get_joomla_menu_items", "get_joomla_modules"}:
            data = {"data": [data["data"]]}
        return httpx.Response(201 if r.method == "POST" else 200, json=data)

    server, api = factory(handler)
    try:
        assert (await server.call_tool(name, args)).structured_content["ok"]
        assert calls[-1].method == method and calls[-1].url.path.endswith("/" + path)
        if name == "get_joomla_menu_items":
            assert calls[0].url.params["filter[menutype]"] == "mainmenu"
        if name in {"create_menu_item", "create_custom_module"}:
            assert json.loads(calls[-1].content)["published"] == 0
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_wrong_module_type(factory):
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(200, json=resource(module="mod_menu"))

    server, api = factory(handler)
    try:
        with pytest.raises(ToolError):
            await server.call_tool(
                "update_module",
                {"module_id": 3, "expected_title": "Existing", "content": "wrong"},
            )
        assert [r.method for r in calls] == ["GET"]
    finally:
        await api.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "link",
    ["javascript:alert(1)", "//evil.test", "https://user:pass@example.com", "../path"],
)
async def test_menu_link_validation(factory, link):
    calls = []
    server, api = factory(lambda r: calls.append(r))
    try:
        with pytest.raises(ToolError):
            await server.call_tool(
                "create_menu_item",
                {"title": "Bad", "menutype": "mainmenu", "link": link},
            )
        assert not calls
    finally:
        await api.close()
