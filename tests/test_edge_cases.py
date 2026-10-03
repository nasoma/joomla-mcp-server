import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
import subprocess
import sys
import os

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from joomlamcp.config import Settings
from joomlamcp.client import JoomlaClient
from conftest import resource

ENV = {
    "JOOMLA_BASE_URL": "https://joomla.invalid",
    "BEARER_TOKEN": "dummy-test-token",
    "JOOMLA_READ_RETRIES": "0",
}


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.ConnectError])
async def test_network_failure_safe(error):
    def respond(r):
        raise error("private credentials dummy-test-token", request=r)

    api = JoomlaClient(Settings.from_env(ENV), httpx.MockTransport(respond))
    try:
        with pytest.raises(ToolError) as exc:
            await api.listing("content/articles", 20, 0)
        assert "private" not in str(exc.value) and "dummy-test-token" not in str(
            exc.value
        )
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_response_size_and_id_mismatch():
    api = JoomlaClient(
        Settings.from_env({**ENV, "JOOMLA_MAX_RESPONSE_BYTES": "1024"}),
        httpx.MockTransport(
            lambda r: httpx.Response(200, json={"data": [], "padding": "x" * 2048})
        ),
    )
    try:
        with pytest.raises(ToolError, match="size limit"):
            await api.listing("content/articles", 20, 0)
    finally:
        await api.close()
    api = JoomlaClient(
        Settings.from_env(ENV),
        httpx.MockTransport(lambda r: httpx.Response(200, json=resource(4))),
    )
    try:
        with pytest.raises(ToolError, match="different resource ID"):
            await api.detail("content/articles", 3)
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_null_detail_and_bad_pagination():
    for data, operation in [
        ({"data": None}, "detail"),
        ({"data": [], "meta": None}, "list"),
        ({"data": [resource()["data"]] * 2}, "list"),
    ]:
        api = JoomlaClient(
            Settings.from_env(ENV),
            httpx.MockTransport(lambda r: httpx.Response(200, json=data)),
        )
        try:
            with pytest.raises(ToolError):
                if operation == "detail":
                    await api.detail("content/articles", 3)
                else:
                    await api.listing("content/articles", 1, 0)
        finally:
            await api.close()


@pytest.mark.asyncio
async def test_retry_after_limits(monkeypatch):
    api = JoomlaClient(
        Settings.from_env(ENV), httpx.MockTransport(lambda r: httpx.Response(429))
    )
    try:
        assert api._delay("60", 0) is None
        assert api._delay("invalid", 0) is None
        assert api._delay("0", 0) == 0
        assert (
            0
            <= api._delay(
                format_datetime(datetime.now(timezone.utc) + timedelta(seconds=2)), 0
            )
            <= 2
        )
    finally:
        await api.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,args",
    [
        ("get_joomla_article", {"article_id": 3}),
        ("get_joomla_categories", {}),
        (
            "manage_article_state",
            {"article_id": 3, "target_state": 1, "expected_title": "Existing"},
        ),
    ],
)
async def test_remaining_article_tools(factory, name, args):
    calls = []

    def handler(r):
        calls.append(r)
        if r.method == "PATCH":
            return httpx.Response(204)
        data = resource(3, state=0)
        if name == "get_joomla_categories":
            data = {"data": [data["data"]]}
        return httpx.Response(200, json=data)

    server, api = factory(handler)
    try:
        assert (await server.call_tool(name, args)).structured_content["ok"]
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_stale_noop_and_invalid_state(factory):
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(200, json=resource(3, state="1", modified="new"))

    server, api = factory(handler)
    try:
        with pytest.raises(ToolError, match="changed"):
            await server.call_tool(
                "update_article",
                {
                    "article_id": 3,
                    "title": "New",
                    "expected_title": "Existing",
                    "expected_modified": "old",
                },
            )
        result = await server.call_tool(
            "manage_article_state",
            {"article_id": 3, "target_state": 1, "expected_title": "Existing"},
        )
        assert result.structured_content["changed"] is False
        with pytest.raises(ToolError):
            await server.call_tool(
                "manage_article_state",
                {"article_id": 3, "target_state": -1, "expected_title": "Existing"},
            )
        assert all(r.method == "GET" for r in calls)
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_tags_replace_clear(factory):
    calls = []

    def handler(r):
        calls.append(r)
        return (
            httpx.Response(200, json=resource())
            if r.method == "GET"
            else httpx.Response(204)
        )

    server, api = factory(handler)
    try:
        await server.call_tool(
            "update_article",
            {"article_id": 3, "expected_title": "Existing", "tags": []},
        )
        assert json.loads(calls[-1].content) == {"tags": []}
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_no_api_body_in_mcp_error(factory):
    server, api = factory(
        lambda r: httpx.Response(403, text="private data and secret token")
    )
    try:
        with pytest.raises(ToolError) as exc:
            await server.call_tool("get_joomla_articles", {})
        assert "403" in str(exc.value) and "private data" not in str(exc.value)
    finally:
        await api.close()


def test_config_exit_without_traceback():
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"JOOMLA_BASE_URL", "BEARER_TOKEN"}
    }
    result = subprocess.run(
        [sys.executable, "main.py"], capture_output=True, text=True, env=env, timeout=10
    )
    assert result.returncode == 2 and "Configuration error" in result.stderr
    assert not result.stdout and "Traceback" not in result.stderr


@pytest.mark.asyncio
async def test_lifespan_closes_shared_client(factory):
    server, api = factory(lambda r: httpx.Response(200, json={"data": []}))
    async with server.settings.lifespan(server):
        await server.call_tool("get_joomla_articles", {})
        await server.call_tool("get_joomla_categories", {})
        assert not api.http.is_closed
    assert api.http.is_closed
