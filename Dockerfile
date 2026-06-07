# syntax=docker/dockerfile:1

FROM node:22-bookworm-slim AS web-build
WORKDIR /app/apps/web
RUN corepack enable && corepack prepare pnpm@10.28.1 --activate
COPY apps/web/package.json apps/web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY apps/web/ ./
ENV VITE_API_BASE_URL=""
RUN pnpm run build

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS api-runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/apps/api/.venv/bin:$PATH" \
    CD_STATIC_DIR="/app/static" \
    CD_DATABASE_URL="sqlite:////data/classroom_downloader.db" \
    CD_GOOGLE_TOKEN_PATH="/data/tokens/google-user.json" \
    CD_GOOGLE_OAUTH_STATE_PATH="/data/tokens/google-oauth-state.txt" \
    CD_GRADING_CACHE_PATH="/data/cache/grading" \
    CD_EXPORT_CACHE_PATH="/data/cache/exports" \
    CD_LLM_MODEL_CATALOG_CACHE_PATH="/data/cache/llm/model-prices.json" \
    CD_LOG_RICH="false" \
    CD_LOG_FORMAT="json"

COPY apps/api/pyproject.toml apps/api/uv.lock ./apps/api/
WORKDIR /app/apps/api
RUN uv sync --locked --no-dev

WORKDIR /app
COPY apps/api/config ./apps/api/config
COPY apps/api/src ./apps/api/src
COPY --from=web-build /app/apps/web/dist ./static

RUN mkdir -p /data/tokens /data/cache/grading /data/cache/exports /data/cache/llm \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /data

USER appuser
WORKDIR /app/apps/api
EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"

CMD ["python", "-m", "uvicorn", "classroom_downloader.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
