"""Validated image upload, bounded media results and article image metadata."""

import base64
import binascii
from io import BytesIO
from pathlib import PurePosixPath
import re
from typing import Annotated, Any, Literal
from urllib.parse import quote, urlsplit
import warnings
from PIL import Image, UnidentifiedImageError
from pydantic import Field
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from .client import JoomlaClient
from .models import Id, Limit, Offset, Title, Meta
from .safety import READ, WRITE, check_identity

MediaPath = Annotated[str, Field(min_length=1, max_length=512)]
Base64Image = Annotated[str, Field(min_length=1, max_length=27_000_000)]
Mime = Literal["image/png", "image/jpeg", "image/gif", "image/webp"]
FORMATS = {
    "PNG": ("image/png", {".png"}),
    "JPEG": ("image/jpeg", {".jpg", ".jpeg"}),
    "GIF": ("image/gif", {".gif"}),
    "WEBP": ("image/webp", {".webp"}),
}


def validate_path(path: str, *, file: bool = False) -> str:
    # Restrict uploads/reads to the built-in images adapter, without arbitrary providers.
    if not path.startswith("local-images:/"):
        raise ToolError(
            "Media path must use local-images:/ (the built-in images adapter)."
        )
    suffix = path[len("local-images:/") :]
    parts = suffix.rstrip("/").split("/") if suffix.rstrip("/") else []
    if any(
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", p) or ".." in p for p in parts
    ):
        raise ToolError("Media path contains unsafe or unsupported path segments.")
    if file and (not parts or path.endswith("/") or not PurePosixPath(path).suffix):
        raise ToolError("A media filename with a supported extension is required.")
    return path


def parse_media(value: Any) -> dict:
    if not isinstance(value, dict) or not isinstance(value.get("attributes"), dict):
        raise ToolError("Invalid Joomla media resource.")
    attributes = value["attributes"]
    if not isinstance(attributes.get("path"), str) or not attributes["path"]:
        raise ToolError("Joomla media resource has no path.")
    # Never expose embedded base64 or temporary download credentials.
    allowed = {
        "type",
        "name",
        "path",
        "extension",
        "size",
        "mime_type",
        "width",
        "height",
        "adapter",
        "url",
    }
    return {
        "path": attributes["path"],
        "attributes": {k: v for k, v in attributes.items() if k in allowed},
    }


def validate_image(content: str, path: str, mime: str, max_bytes: int) -> None:
    if len(content) > 4 * ((max_bytes + 2) // 3):
        raise ToolError("Image exceeds configured upload size limit.")
    try:
        raw = base64.b64decode(content, validate=True)
    except binascii.Error, ValueError:
        raise ToolError("Image content must be valid base64.") from None
    if not raw or len(raw) > max_bytes:
        raise ToolError("Image is empty or exceeds configured upload size limit.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                if image.width * image.height > 25_000_000:
                    raise ToolError("Image dimensions exceed 25 million pixels.")
                contract = FORMATS.get(image.format)
                if (
                    not contract
                    or mime != contract[0]
                    or PurePosixPath(path).suffix.lower() not in contract[1]
                ):
                    raise ToolError(
                        "Image content, MIME type and filename extension must match."
                    )
                image.verify()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise ToolError("Invalid, corrupted or oversized image content.") from None


def image_reference(value: str) -> str:
    if value == "":
        return value
    parsed = urlsplit(value)
    if parsed.scheme:
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ToolError(
                "Article image references must be HTTPS URLs or relative images/ paths."
            )
        if any(ord(c) < 32 for c in value):
            raise ToolError("Invalid image reference.")
        return value
    if not value.startswith("images/"):
        raise ToolError("Relative image references must start with images/.")
    validate_path("local-images:/" + value[len("images/") :], file=True)
    return value


def register(server: MCPServer, client: JoomlaClient) -> None:
    @server.tool(annotations=READ)
    async def get_joomla_media(
        path: MediaPath = "local-images:/",
        limit: Limit = 20,
        offset: Offset = 0,
        search: Meta | None = None,
    ) -> dict[str, Any]:
        """List media in the images adapter, without file contents. Joomla returns a whole directory; results are sliced locally and response bytes remain bounded."""
        validate_path(path)
        params = {"path": path, "content": "0", "url": "1", "temp": "0"}
        if search is not None:
            params["filter[search]"] = search
        data, _ = await client.request("GET", "media/files", params=params)
        if not isinstance(data["data"], list):
            raise ToolError("Expected a Joomla media list.")
        rows = data["data"]
        has_next = offset + limit < len(rows)
        return {
            "ok": True,
            "data": [parse_media(row) for row in rows[offset : offset + limit]],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "count": len(rows[offset : offset + limit]),
                "total": len(rows),
                "has_next": has_next,
                "next_offset": offset + limit if has_next else None,
                "server_paginated": False,
            },
        }

    @server.tool(annotations=READ)
    async def get_joomla_media_file(path: MediaPath) -> dict[str, Any]:
        """Read image file metadata by adapter path; base64 content and temporary URLs are excluded."""
        validate_path(path, file=True)
        data, _ = await client.request(
            "GET",
            "media/files/" + quote(path, safe="/"),
            params={"content": "0", "url": "1", "temp": "0"},
        )
        return {"ok": True, "data": parse_media(data["data"])}

    @server.tool(annotations=WRITE)
    async def upload_media(
        path: MediaPath, content_base64: Base64Image, mime_type: Mime
    ) -> dict[str, Any]:
        """Upload a new PNG/JPEG/GIF/WebP image to local-images:/folder/name.ext. Content must be base64 and match MIME/extension; never overwrites."""
        client.require_write()
        validate_path(path, file=True)
        validate_image(
            content_base64, path, mime_type, client.settings.max_upload_bytes
        )
        data, _ = await client.request(
            "POST",
            "media/files",
            payload={"path": path, "content": content_base64, "override": False},
        )
        if data is None:
            raise ToolError(
                "Upload succeeded without metadata; verify the path before retrying."
            )
        return {"ok": True, "data": parse_media(data["data"])}

    @server.tool(annotations=WRITE)
    async def update_article_images(
        article_id: Id,
        expected_title: Title,
        image_intro: Meta | None = None,
        image_intro_alt: Meta | None = None,
        image_intro_caption: Meta | None = None,
        image_fulltext: Meta | None = None,
        image_fulltext_alt: Meta | None = None,
        image_fulltext_caption: Meta | None = None,
        expected_modified: Meta | None = None,
    ) -> dict[str, Any]:
        """Update supplied article image/alt/caption properties while preserving other image metadata. Empty strings clear properties."""
        client.require_write()
        updates = {
            k: v
            for k, v in [
                ("image_intro", image_intro),
                ("image_intro_alt", image_intro_alt),
                ("image_intro_caption", image_intro_caption),
                ("image_fulltext", image_fulltext),
                ("image_fulltext_alt", image_fulltext_alt),
                ("image_fulltext_caption", image_fulltext_caption),
            ]
            if v is not None
        }
        if not updates:
            raise ToolError("Provide at least one image property to update.")
        for key in ["image_intro", "image_fulltext"]:
            if key in updates:
                image_reference(updates[key])
        article = await client.detail("content/articles", article_id)
        check_identity(article, expected_title, expected_modified, required=True)
        existing = article.attributes.get("images", {})
        if not isinstance(existing, dict):
            raise ToolError(
                "Article image metadata is not an object; refusing to overwrite it."
            )
        return await client.update(
            "content/articles", article, {"images": {**existing, **updates}}
        )
