"""Validated, explicit environment configuration (never logs credentials)."""

import os
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)
    base_url: str
    token: SecretStr
    read_only: bool = False
    allow_trusted_html: bool = False
    enable_users: bool = False
    allow_local_http: bool = False
    timeout: float = Field(default=20, gt=0, le=120)
    read_retries: int = Field(default=2, ge=0, le=3)
    max_response_bytes: int = Field(default=2_000_000, ge=1024, le=10_000_000)
    max_upload_bytes: int = Field(default=5_000_000, ge=1024, le=20_000_000)
    joomla_version: str = Field(default="5", pattern=r"^[45]$")

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        values = os.environ if env is None else env
        url = values.get("JOOMLA_BASE_URL", "").strip().rstrip("/")
        token = values.get("BEARER_TOKEN", "").strip()
        if not url or not token:
            raise ValueError(
                "JOOMLA_BASE_URL and BEARER_TOKEN must be set and nonempty."
            )
        if any(c.isspace() or ord(c) < 32 for c in token):
            raise ValueError(
                "BEARER_TOKEN must not contain whitespace or control characters."
            )

        def flag(name: str) -> bool:
            value = values.get(name, "false").lower()
            if value not in {"true", "false", "1", "0"}:
                raise ValueError(f"{name} must be true/false or 1/0.")
            return value in {"true", "1"}

        local = flag("JOOMLA_ALLOW_LOCAL_HTTP")
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            raise ValueError("JOOMLA_BASE_URL is not a valid URL.") from None
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or any(c.isspace() for c in url)
            or "%" in parsed.netloc
            or "\\" in url
            or (port is not None and port == 0)
        ):
            raise ValueError(
                "JOOMLA_BASE_URL must be a site URL without credentials, query or fragment."
            )
        if parsed.scheme != "https" and not (
            parsed.scheme == "http"
            and local
            and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError(
                "HTTPS is required; local HTTP needs JOOMLA_ALLOW_LOCAL_HTTP=true."
            )
        if "/api/index.php" in parsed.path:
            raise ValueError(
                "JOOMLA_BASE_URL must be the site root, not an API endpoint."
            )
        try:
            return cls(
                base_url=url,
                token=SecretStr(token),
                allow_local_http=local,
                read_only=flag("JOOMLA_READ_ONLY"),
                allow_trusted_html=flag("JOOMLA_ALLOW_TRUSTED_HTML"),
                enable_users=flag("JOOMLA_ENABLE_USERS"),
                timeout=values.get("JOOMLA_TIMEOUT", "20"),
                read_retries=values.get("JOOMLA_READ_RETRIES", "2"),
                max_response_bytes=values.get("JOOMLA_MAX_RESPONSE_BYTES", "2000000"),
                max_upload_bytes=values.get("JOOMLA_MAX_UPLOAD_BYTES", "5000000"),
                joomla_version=values.get("JOOMLA_VERSION", "5"),
            )
        except ValidationError:
            raise ValueError(
                "Invalid numeric limits or JOOMLA_VERSION (supported: 4 or 5)."
            ) from None
