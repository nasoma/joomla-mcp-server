FROM python:3.14.8-slim

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --locked --no-dev --no-install-project

COPY main.py ./
ENV PATH="/app/.venv/bin:$PATH"

# The server communicates over stdin/stdout; no HTTP port is needed.
CMD ["python", "main.py"]
