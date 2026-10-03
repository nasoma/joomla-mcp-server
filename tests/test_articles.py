import json
import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from joomlamcp.content import convert_content, infer_title
from conftest import resource


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [("introtext", ""), ("fulltext", "Body"), ("metadesc", ""), ("title", "New")],
)
async def test_independent_updates(factory, field, value):
    calls = []

    def handler(r):
        calls.append(r)
        return (
            httpx.Response(200, json=resource(int(r.url.path.rsplit("/", 1)[1])))
            if r.method == "GET"
            else httpx.Response(204)
        )

    server, api = factory(handler)
    try:
        result = await server.call_tool(
            "update_article",
            {"article_id": 3, "expected_title": "Existing", field: value},
        )
        assert not result.is_error
        payload = json.loads(calls[-1].content)
        assert set(payload) == {field}
        assert payload[field] == ("<p>Body</p>" if value == "Body" else value)
        assert len(calls) == 2
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_category_detail_and_draft(factory):
    calls = []

    def handler(r):
        calls.append(r)
        return (
            httpx.Response(200, json=resource(99))
            if r.method == "GET"
            else httpx.Response(201, json=resource(123))
        )

    server, api = factory(handler)
    try:
        result = await server.call_tool(
            "create_article", {"article_text": "**Hello**", "category_id": 99}
        )
        assert result.structured_content["data"]["id"] == "123"
        assert calls[0].url.path.endswith("/content/categories/99")
        payload = json.loads(calls[-1].content)
        assert payload["title"] == "Hello" and payload["state"] == 0
        assert "alias" not in payload
    finally:
        await api.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "args",
    [
        {"expected_title": "Wrong", "confirm": True},
        {"expected_title": "Existing"},
        {"confirm": True},
    ],
)
async def test_trash_safety(factory, args):
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(200, json=resource(3, state=1))

    server, api = factory(handler)
    try:
        with pytest.raises(ToolError):
            await server.call_tool("move_article_to_trash", {"article_id": 3, **args})
        assert all(r.method == "GET" for r in calls)
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_trash_one_read_etag(factory):
    calls = []

    def handler(r):
        calls.append(r)
        return (
            httpx.Response(200, json=resource(3), headers={"ETag": '"v1"'})
            if r.method == "GET"
            else httpx.Response(204)
        )

    server, api = factory(handler)
    try:
        await server.call_tool(
            "move_article_to_trash",
            {"article_id": 3, "expected_title": "Existing", "confirm": True},
        )
        assert [r.method for r in calls] == ["GET", "PATCH"]
        assert calls[-1].headers["If-Match"] == '"v1"'
        assert json.loads(calls[-1].content) == {"state": -2}
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_pagination_filters(factory):
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(
            200,
            json={
                "data": [resource()["data"]],
                "links": {"next": "https://evil.invalid"},
                "meta": {"total-pages": 3},
            },
        )

    server, api = factory(handler)
    try:
        result = await server.call_tool(
            "get_joomla_articles",
            {"limit": 1, "offset": 2, "category_id": 7, "search": "hello", "state": 0},
        )
        data = result.structured_content
        assert data["pagination"]["next_offset"] == 3
        assert calls[0].url.params["filter[category]"] == "7"
        assert calls[0].url.params["filter[state]"] == "0"
        assert calls[0].url.params["page[offset]"] == "2"
        assert len(calls) == 1  # untrusted next link is never followed
    finally:
        await api.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_id", [True, 0, -1, "3"])
async def test_strict_ids(factory, bad_id):
    calls = []
    server, api = factory(lambda r: calls.append(r))
    try:
        with pytest.raises(ToolError):
            await server.call_tool("get_joomla_article", {"article_id": bad_id})
        assert not calls
    finally:
        await api.close()


@pytest.mark.parametrize("mode", ["html", "markdown"])
def test_safe_html(mode):
    html = convert_content(
        '<a href="javascript:alert(1)">x</a><img src="https://a.test/x.png" onerror="x"><script>alert(1)</script><table><tr><td>x</td></tr></table>',
        mode,
        False,
    )
    assert "javascript:" not in html and "onerror" not in html and "<script" not in html
    assert "<table>" in html and "<img" in html


def test_trusted_html_and_title():
    with pytest.raises(ToolError):
        convert_content('<p style="color:red">x</p>', "trusted_html", False)
    source = '<p style="color:red">x</p>'
    assert convert_content(source, "trusted_html", True) == source
    assert infer_title("**Héllo** world") == "Héllo world"
