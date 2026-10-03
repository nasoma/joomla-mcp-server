FROM python:3.14.8-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.22
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY joomlamcp ./joomlamcp
RUN uv sync --locked --no-dev --no-editable

FROM python:3.14.8-slim AS runtime
RUN groupadd --gid 10001 joomla && useradd --uid 10001 --gid joomla --create-home joomla
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
# Stdio requires stdin to remain open; no network port is exposed.
CMD ["joomla-mcp"]
