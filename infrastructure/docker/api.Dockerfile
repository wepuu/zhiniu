FROM ghcr.io/astral-sh/uv:0.8.14 AS uv
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/app/.venv/bin:$PATH
WORKDIR /app
RUN useradd --create-home --uid 10001 zhaoniu
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
COPY apps/api ./apps/api
COPY apps/worker ./apps/worker
COPY infrastructure/migrations ./infrastructure/migrations
RUN uv sync --frozen --no-dev
USER zhaoniu
CMD ["uvicorn", "zhaoniu_api.main:app", "--app-dir", "apps/api/src", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "172.16.0.0/12"]
