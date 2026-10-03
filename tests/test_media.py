import base64
from io import BytesIO
import json
import httpx
from PIL import Image
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from joomlamcp.media import validate_path, validate_image
from conftest import resource


def png():
    buf = BytesIO()
    Image.new("RGB", (2, 2)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def media(path="local-images:/photo.png"):
    return {
        "data": {
            "id": "0",
            "attributes": {
                "path": path,
                "name": "photo.png",
                "content": "private",
                "tempUrl": "private",
            },
        }
    }


@pytest.mark.parametrize(
    "path",
    [
        "local-images:/../x.png",
        "local-images:/%2e%2e/x.png",
        "/etc/passwd",
        "local-images:/a//b.png",
        "local-images:/a\\b.png",
        "local-images:/.hidden/x.png",
    ],
)
def test_bad_paths(path):
    with pytest.raises(ToolError):
        validate_path(path, file=True)


@pytest.mark.parametrize(
    "content,path,mime,max_bytes",
    [
        ("invalid", "local-images:/x.png", "image/png", 10000),
        (
            base64.b64encode(b"<svg/>").decode(),
            "local-images:/x.png",
            "image/png",
            10000,
        ),
        (png(), "local-images:/x.jpg", "image/png", 10000),
        (png(), "local-images:/x.png", "image/jpeg", 10000),
        (png(), "local-images:/x.png", "image/png", 1),
    ],
)
def test_bad_uploads(content, path, mime, max_bytes):
    with pytest.raises(ToolError):
        validate_image(content, path, mime, max_bytes)


@pytest.mark.asyncio
async def test_media_tools(factory):
    calls = []

    def handler(r):
        calls.append(r)
        data = media()
        if r.url.path.endswith("/media/files") and r.method == "GET":
            data = {"data": [media()["data"], media("local-images:/other.png")["data"]]}
        if "/content/articles/" in r.url.path:
            return (
                httpx.Response(204)
                if r.method == "PATCH"
                else httpx.Response(
                    200, json=resource(3, images={"image_fulltext": "images/keep.png"})
                )
            )
        return httpx.Response(201 if r.method == "POST" else 200, json=data)

    server, api = factory(handler)
    try:
        listing = (
            await server.call_tool("get_joomla_media", {"limit": 1})
        ).structured_content
        assert (
            listing["pagination"]["next_offset"] == 1
            and not listing["pagination"]["server_paginated"]
        )
        assert len(listing["data"]) == 1
        detail = (
            await server.call_tool(
                "get_joomla_media_file", {"path": "local-images:/photo.png"}
            )
        ).structured_content
        assert (
            "content" not in detail["data"]["attributes"]
            and "tempUrl" not in detail["data"]["attributes"]
        )
        await server.call_tool(
            "upload_media",
            {
                "path": "local-images:/photo.png",
                "content_base64": png(),
                "mime_type": "image/png",
            },
        )
        payload = json.loads(calls[-1].content)
        assert (
            payload["override"] is False
            and payload["path"] == "local-images:/photo.png"
        )
        await server.call_tool(
            "update_article_images",
            {
                "article_id": 3,
                "expected_title": "Existing",
                "image_intro": "images/photo.png",
                "image_intro_alt": "Photo",
            },
        )
        assert json.loads(calls[-1].content)["images"] == {
            "image_fulltext": "images/keep.png",
            "image_intro": "images/photo.png",
            "image_intro_alt": "Photo",
        }
    finally:
        await api.close()
