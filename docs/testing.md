# Verification and integration limits

Run `uv sync --locked`, then `uv run --locked pytest --cov=joomlamcp` and
`uv run --locked black --check main.py joomlamcp tests`. Development dependencies are isolated
from production. No live-site credentials are needed, and no test makes a live Joomla request.

Tests exercise every registered tool's safe-read errors or read-only write rejection, and
all feature families' success payloads. Tool tests run with both JOOMLA_VERSION=4 and =5.
These are synthetic JSON:API responses checked against official Joomla 4.4.13 and 5.4.0
source contracts; they are not captured integration fixtures and do not prove server acceptance.
Other cases cover invalid configuration, nullable/invalid response shapes, status failures,
network timeouts, Retry-After, response limits, independent updates, empty values, title/timestamp
checks, tags, image validation, field name/type validation and user-data filtering.

`uv run python tests/smoke_stdio.py .venv/bin/joomla-mcp` checks an actual stdio subprocess,
tool schemas/annotations and a read-only mutation error using dummy configuration. It never
calls Joomla. The same script can wrap Docker; see `.github/workflows/ci.yml`.

CI builds both package artifacts and the Docker image, checks the non-root image user and
runs Docker stdio/read-only smoke. CI has read-only repository permissions and no live token.
A dedicated staging Joomla 4/5 site is still needed to validate extension-specific behavior.
Do not run live mutations as part of ordinary verification. Any staging integration suite
should be opt-in, use a dedicated least-privilege account and isolated disposable content.

Smithery's schema uses standard JSON Schema writeOnly metadata for the token; this is not
an assurance that every host masks or stores it securely. Runtime validation is authoritative.
