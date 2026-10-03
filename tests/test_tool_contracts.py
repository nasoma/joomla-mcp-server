"""Cross-cutting guarantees for every registered tool, on both Joomla contracts."""

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError


def arguments(schema):
    args = {}
    for name in schema.get("required", []):
        spec = schema["properties"][name]
        if name == "path":
            args[name] = "local-images:/photo.png"
        elif name == "name":
            args[name] = "color"
        elif name == "values":
            args[name] = {"color": "safe"}
        elif "enum" in spec:
            args[name] = spec["enum"][0]
        elif spec.get("type") == "integer":
            args[name] = max(
                1, spec.get("minimum", 1), spec.get("exclusiveMinimum", 0) + 1
            )
        elif spec.get("type") == "boolean":
            args[name] = False
        else:
            args[name] = "Existing"
    return args


@pytest.mark.asyncio
async def test_all_read_tools_safe_failure(factory):
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(403, text="private upstream content")

    server, api = factory(handler, JOOMLA_ENABLE_USERS="true")
    try:
        for tool in await server.list_tools():
            if not tool.annotations.read_only_hint:
                continue
            calls.clear()
            with pytest.raises(ToolError) as exc:
                await server.call_tool(tool.name, arguments(tool.input_schema))
            assert "403" in str(exc.value), tool.name
            assert "private" not in str(exc.value), tool.name
            assert len(calls) == 1 and calls[0].method == "GET", tool.name
    finally:
        await api.close()


@pytest.mark.asyncio
async def test_all_write_tools_read_only_no_http(factory):
    calls = []
    server, api = factory(
        lambda r: calls.append(r), JOOMLA_READ_ONLY="true", JOOMLA_ENABLE_USERS="true"
    )
    try:
        for tool in await server.list_tools():
            assert tool.output_schema is not None, tool.name
            if tool.annotations.read_only_hint:
                continue
            with pytest.raises(ToolError) as exc:
                await server.call_tool(tool.name, arguments(tool.input_schema))
            assert "disabled" in str(exc.value), tool.name
            assert not calls, tool.name
    finally:
        await api.close()
