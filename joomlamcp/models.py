"""Public argument constraints and normalized JSON:API resources."""

from typing import Annotated, Literal, Any
from pydantic import BaseModel, Field, ConfigDict

Id = Annotated[int, Field(strict=True, gt=0)]
Limit = Annotated[int, Field(strict=True, ge=1, le=100)]
Offset = Annotated[int, Field(strict=True, ge=0, le=1_000_000)]
Title = Annotated[str, Field(min_length=1, max_length=255, pattern=r"\S")]
Text = Annotated[str, Field(max_length=1_000_000)]
Meta = Annotated[str, Field(max_length=1024)]
State = Annotated[int, Field(strict=True, ge=-2, le=2)]
ContentMode = Literal["markdown", "html", "trusted_html"]


class Resource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    attributes: dict[str, Any]
    etag: str | None = None

    def public(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)
