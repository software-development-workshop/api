FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN uv sync --locked --no-dev

EXPOSE 8001
CMD ["sh", "-c", "uv run --no-sync alembic upgrade head && uv run --no-sync uvicorn posts.main:app --host 0.0.0.0 --port 8001"]
