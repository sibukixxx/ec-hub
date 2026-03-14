# syntax=docker/dockerfile:1
FROM python:3.11-slim AS backend

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install dependencies first (cache layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Copy source code and install project
COPY README.md ./
COPY src/ src/
COPY config/ config/
COPY tests/ tests/
RUN uv sync --frozen

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "ec_hub.api:app", "--host", "0.0.0.0", "--port", "8000"]

# Frontend stage
FROM node:20-slim AS frontend

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

COPY frontend/package.json frontend/pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install

COPY frontend/ .

EXPOSE 5173

CMD ["pnpm", "dev", "--host", "0.0.0.0"]
