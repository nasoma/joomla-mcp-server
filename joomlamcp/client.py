"""Pooled Joomla JSON:API client with bounded reads and safe errors."""

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import logging
from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError

from .config import Settings
from .models import Resource

logger = logging.getLogger(__name__)


def parse_resource(value: Any, etag: str | None = None) -> Resource:
    if not isinstance(value, dict) or not isinstance(value.get("attributes"), dict):
        raise ToolError("Invalid Joomla response: expected resource attributes.")
    attrs = value["attributes"]
    resource_id = value.get("id", attrs.get("id"))
    if (
        type(resource_id) not in {int, str}
        or not str(resource_id).isdigit()
        or int(resource_id) <= 0
    ):
        raise ToolError("Invalid Joomla response: missing positive resource ID.")
    return Resource(id=str(resource_id), attributes=attrs, etag=etag)


class JoomlaClient:
    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ):
        self.settings = settings
        self.http = httpx.AsyncClient(
            timeout=settings.timeout,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
            headers={
                "Accept": "application/vnd.api+json",
                "Authorization": f"Bearer {settings.token.get_secret_value()}",
                "User-Agent": "JoomlaMCP/0.2",
            },
        )

    async def close(self) -> None:
        await self.http.aclose()

    def require_write(self) -> None:
        if self.settings.read_only:
            raise ToolError("Writes are disabled by JOOMLA_READ_ONLY.")

    def _delay(self, retry_after: str | None, attempt: int) -> float | None:
        if not retry_after:
            return min(0.25 * 2**attempt, 2)
        try:
            delay = float(retry_after)
        except ValueError:
            try:
                delay = (
                    parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)
                ).total_seconds()
            except ValueError, TypeError, OverflowError:
                return None
        # Never wait indefinitely or retry before a long server-requested delay.
        return max(0, delay) if delay <= 5 else None

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        payload: dict | None = None,
        etag: str | None = None,
    ) -> tuple[Any, str | None]:
        if method != "GET":
            self.require_write()
        if (
            path.startswith("/")
            or ":" in path
            or ".." in path
            or "?" in path
            or "#" in path
        ):
            raise ToolError("Invalid internal API path.")
        attempts = self.settings.read_retries + 1 if method == "GET" else 1
        for attempt in range(attempts):
            try:
                async with self.http.stream(
                    method,
                    f"{self.settings.base_url}/api/index.php/v1/{path}",
                    params=params,
                    json=payload,
                    headers={"If-Match": etag} if etag else None,
                ) as response:
                    status = response.status_code
                    logger.info("Joomla operation method=%s status=%s", method, status)
                    if (
                        method == "GET"
                        and status in {429, 502, 503, 504}
                        and attempt + 1 < attempts
                    ):
                        delay = self._delay(
                            response.headers.get("Retry-After"), attempt
                        )
                        if delay is not None:
                            await asyncio.sleep(delay)
                            continue
                    if status not in {200, 201, 204}:
                        hints = {
                            401: "Check API authentication.",
                            403: "Check Joomla permissions.",
                            404: "Resource or Web Services plugin unavailable.",
                            409: "Resource conflict.",
                            412: "Resource changed; read it again.",
                            429: "Rate limited; try later.",
                        }
                        raise ToolError(
                            f"Joomla HTTP {status}. {hints.get(status, 'API request failed; check server logs.')}"
                        )
                    if status == 204:
                        return None, response.headers.get("ETag")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > self.settings.max_response_bytes:
                            raise ToolError(
                                "Joomla response exceeds configured size limit; use a smaller page."
                            )
                    try:
                        data = json.loads(body)
                    except ValueError, UnicodeDecodeError:
                        raise ToolError(
                            "Invalid Joomla response: expected JSON."
                        ) from None
                    if not isinstance(data, dict) or "data" not in data:
                        raise ToolError(
                            "Invalid Joomla response: expected JSON:API data."
                        )
                    return data, response.headers.get("ETag")
            except httpx.HTTPError:
                if method == "GET" and attempt + 1 < attempts:
                    await asyncio.sleep(min(0.25 * 2**attempt, 2))
                    continue
                raise ToolError(
                    "Joomla network request failed or timed out; check connectivity."
                ) from None
        raise ToolError("Joomla read attempts exhausted.")

    async def detail(self, path: str, resource_id: int) -> Resource:
        data, etag = await self.request("GET", f"{path}/{resource_id}")
        if not data or data.get("data") is None:
            raise ToolError("Joomla resource was not found.")
        resource = parse_resource(data["data"], etag)
        if resource.id != str(resource_id):
            raise ToolError(
                "Joomla returned a different resource ID; refusing operation."
            )
        return resource

    async def listing(
        self, path: str, limit: int, offset: int, filters: dict | None = None
    ) -> dict:
        data, _ = await self.request(
            "GET",
            path,
            params={"page[limit]": limit, "page[offset]": offset, **(filters or {})},
        )
        rows = data["data"]
        if not isinstance(rows, list) or len(rows) > limit:
            raise ToolError(
                "Invalid Joomla response: expected a bounded resource list."
            )
        links, meta = data.get("links", {}), data.get("meta", {})
        if not isinstance(links, dict) or not isinstance(meta, dict):
            raise ToolError("Invalid Joomla pagination metadata.")
        return {
            "ok": True,
            "data": [parse_resource(row).public() for row in rows],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "count": len(rows),
                "has_next": bool(links.get("next")),
                "next_offset": offset + limit if links.get("next") else None,
                "total": meta.get("total"),
                "total_pages": meta.get("total-pages"),
            },
        }

    async def create(self, path: str, payload: dict) -> dict:
        data, etag = await self.request("POST", path, payload=payload)
        if not data or data.get("data") is None:
            raise ToolError(
                "Joomla write succeeded but returned no resource; do not retry automatically."
            )
        return {"ok": True, "data": parse_resource(data["data"], etag).public()}

    async def update(self, path: str, resource: Resource, payload: dict) -> dict:
        data, etag = await self.request(
            "PATCH", f"{path}/{resource.id}", payload=payload, etag=resource.etag
        )
        if data is None:
            return {
                "ok": True,
                "data": {"id": resource.id},
                "updated_fields": sorted(payload),
            }
        returned = parse_resource(data["data"], etag)
        if returned.id != resource.id:
            raise ToolError(
                "Joomla write returned an unexpected ID; verify before retrying."
            )
        return {
            "ok": True,
            "data": returned.public(),
            "updated_fields": sorted(payload),
        }

    async def delete(self, path: str, resource: Resource) -> dict:
        await self.request("DELETE", f"{path}/{resource.id}", etag=resource.etag)
        return {"ok": True, "data": {"id": resource.id}, "deleted": True}
