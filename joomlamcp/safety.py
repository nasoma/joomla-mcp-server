from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from .models import Resource

READ = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)
WRITE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=True,
)
DESTRUCTIVE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=False,
    open_world_hint=True,
)


def check_identity(
    resource: Resource,
    expected_title: str | None,
    expected_modified: str | None = None,
    *,
    required: bool = False,
    title_key: str = "title",
) -> None:
    if required and not expected_title:
        raise ToolError(
            "Read the resource and provide its exact expected_title before changing it."
        )
    if (
        expected_title is not None
        and resource.attributes.get(title_key) != expected_title
    ):
        raise ToolError("Resource title does not match expected_title; read it again.")
    if (
        expected_modified is not None
        and resource.attributes.get("modified") != expected_modified
    ):
        raise ToolError("Resource changed since expected_modified; read it again.")


def valid_state(value: int) -> int:
    if type(value) is not int or value not in {1, 0, 2, -2}:
        raise ToolError(
            "State must be 1 (published), 0 (draft), 2 (archived), or -2 (trashed)."
        )
    return value


def require_confirmation(confirm: bool) -> None:
    if confirm is not True:
        raise ToolError(
            "Destructive action requires confirm=true and an exact expected_title."
        )
