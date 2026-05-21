FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH="/app/src" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT="/opt/venv"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --dev

COPY . .

EXPOSE 8000

CMD ["fastapi", "dev", "src/glean/main.py", "--host", "0.0.0.0", "--port", "8000"]
