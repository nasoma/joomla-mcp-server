# Runtime and client design

Configuration is loaded explicitly from environment variables through `Settings.from_env`.
The token is a `SecretStr`; configuration errors omit supplied values. HTTPS is required,
with an explicit loopback-only HTTP development exception. No `.env` file is loaded automatically.

`JoomlaClient` owns a reusable HTTPX client, uses fixed internal endpoint paths,
disables redirects/proxy environment lookup and bounds JSON response sizes. GET requests
retry transient network failures and 429/502/503/504 at most twice. Retry-After seconds or
HTTP dates are honored up to five seconds; longer waits fail immediately for the caller
to reschedule. Mutations are never retried. Read-only mode rejects writes before any request.

JSON:API resources normalize their positive resource ID to a string and preserve attributes.
Null detail data, invalid shapes and malformed JSON become safe MCP ToolErrors. Raw API bodies
and exception strings are never included in errors. Logs contain only operation method/status.
HTTPX/httpcore logs are suppressed by the server so query values and bodies are not logged.

Run foundation checks with `uv run pytest tests/test_foundation.py`. They use MockTransport
and dummy tokens; they never access Joomla. Pytest and Black are development dependencies.
