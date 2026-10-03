import httpx
import pytest
from conftest import resource


@pytest.mark.asyncio
async def test_users_disabled(factory):
    server, api = factory(lambda r: None)
    try:
        assert not any("user" in tool.name for tool in await server.list_tools())
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_users_redacted(factory):
    calls = []

    def handler(r):
        calls.append(r)
        data = resource(
            3,
            name="Test",
            username="tester",
            block=0,
            password="hash",
            email="private@example.com",
            otpKey="secret",
            params={"token": "secret"},
            apiToken="secret",
            groups=[8],
        )
        if r.url.path.endswith("/users"):
            data = {"data": [data["data"]]}
        return httpx.Response(200, json=data)

    server, api = factory(handler, JOOMLA_ENABLE_USERS="true")
    try:
        for name, args in [
            ("get_joomla_users", {}),
            ("get_joomla_user", {"user_id": 3}),
        ]:
            result = (await server.call_tool(name, args)).structured_content
            items = (
                result["data"] if isinstance(result["data"], list) else [result["data"]]
            )
            assert set(items[0]["attributes"]) == {"name", "username", "block"}
        assert all(r.method == "GET" for r in calls)
    finally:
        await api.close()
