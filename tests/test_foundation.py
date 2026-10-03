import asyncio
import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from joomlamcp.config import Settings
from joomlamcp.client import JoomlaClient, parse_resource

ENV = {"JOOMLA_BASE_URL": "https://joomla.invalid", "BEARER_TOKEN": "dummy-test-token"}


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://a:b@example.com",
        "https://example.com?q=1",
        "https://example.com#x",
        "not-url",
        "https://example.com/api/index.php/v1",
        "https://example.com:bad",
    ],
)
def test_invalid_config(url):
    with pytest.raises(ValueError):
        Settings.from_env({**ENV, "JOOMLA_BASE_URL": url})


def test_secrets_and_flags():
    settings = Settings.from_env(ENV)
    assert "dummy-test-token" not in repr(settings)
    with pytest.raises(ValueError):
        Settings.from_env({})
    with pytest.raises(ValueError):
        Settings.from_env({**ENV, "JOOMLA_READ_ONLY": "maybe"})
    assert Settings.from_env(
        {
            **ENV,
            "JOOMLA_BASE_URL": "http://localhost:8080",
            "JOOMLA_ALLOW_LOCAL_HTTP": "true",
        }
    ).allow_local_http


@pytest.mark.parametrize(
    "value",
    [None, [], {}, {"id": True, "attributes": {}}, {"id": "1", "attributes": None}],
)
def test_bad_resources(value):
    with pytest.raises(ToolError):
        parse_resource(value)


def test_resource_ids():
    assert parse_resource({"id": "7", "attributes": {"title": "News"}}).id == "7"
    assert parse_resource({"attributes": {"id": 7}}).id == "7"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
async def test_safe_http_errors(status):
    client = JoomlaClient(
        Settings.from_env({**ENV, "JOOMLA_READ_RETRIES": "0"}),
        httpx.MockTransport(
            lambda r: httpx.Response(status, text="secret body dummy-test-token")
        ),
    )
    try:
        with pytest.raises(ToolError) as exc:
            await client.listing("content/articles", 20, 0)
        assert str(status) in str(exc.value)
        assert "secret" not in str(exc.value)
        assert "dummy-test-token" not in str(exc.value)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_read_retry_only(monkeypatch):
    calls = []

    async def sleep(delay):
        assert delay <= 5

    monkeypatch.setattr(asyncio, "sleep", sleep)

    def respond(r):
        calls.append(r.method)
        return httpx.Response(
            503 if len(calls) == 1 else 200,
            json={"data": []},
            headers={"Retry-After": "0"},
        )

    client = JoomlaClient(Settings.from_env(ENV), httpx.MockTransport(respond))
    try:
        assert (await client.listing("content/articles", 20, 0))["data"] == []
        assert calls == ["GET", "GET"]
        calls.clear()
        with pytest.raises(ToolError):
            await client.create("content/articles", {"title": "x"})
        assert calls == ["POST"]
    finally:
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body", [b"", b"not json", b"[]", b'{"data":null}', b'{"data":{}}']
)
async def test_malformed_list(body):
    client = JoomlaClient(
        Settings.from_env(ENV),
        httpx.MockTransport(lambda r: httpx.Response(200, content=body)),
    )
    try:
        with pytest.raises(ToolError):
            await client.listing("content/articles", 20, 0)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_read_only_no_request():
    calls = []
    client = JoomlaClient(
        Settings.from_env({**ENV, "JOOMLA_READ_ONLY": "true"}),
        httpx.MockTransport(lambda r: calls.append(r)),
    )
    try:
        with pytest.raises(ToolError):
            await client.create("content/articles", {})
        assert not calls
    finally:
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("as_list", [True, False])
async def test_joomla_json_errors_and_redaction(as_list):
    error = {
        "title": "Save failed",
        "detail": "Invalid field. dummy-test-token Bearer other-token password=private /home/user/site/file.php https://private.invalid",
        "trace": "private stack trace",
    }
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(500, json={"errors": [error] if as_list else error})

    client = JoomlaClient(Settings.from_env(ENV), httpx.MockTransport(handler))
    try:
        with pytest.raises(ToolError) as exc:
            await client.request("PATCH", "content/articles/85", payload={"state": 1})
        message = str(exc.value)
        assert "Save failed" in message and "Invalid field" in message
        assert "read the resource before retrying" in message
        for secret in (
            "dummy-test-token",
            "other-token",
            "private",
            "/home/user",
            "stack trace",
        ):
            assert secret not in message
        assert calls == ["PATCH"]
    finally:
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [b"<html>private error page</html>", b"{bad", b"x" * 17000, b'{"errors":null}'],
)
async def test_error_details_fallback(body):
    client = JoomlaClient(
        Settings.from_env(ENV),
        httpx.MockTransport(lambda r: httpx.Response(500, content=body)),
    )
    try:
        with pytest.raises(ToolError) as exc:
            await client.request("GET", "content/articles/85")
        assert "Joomla HTTP 500" in str(exc.value)
        assert "Joomla reports:" not in str(exc.value)
        assert "private" not in str(exc.value)
    finally:
        await client.close()
