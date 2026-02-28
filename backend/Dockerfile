FROM python:3.12-slim

# System deps for pdftotext, EasyOCR, and pdf2image
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project

# Copy source after deps (hot-reload friendly)
COPY src/ src/
COPY alembic.ini .

RUN mkdir -p storage

# Run migrations then start server
CMD uv run alembic upgrade head && \
    uv run uvicorn pbam.main:app --host 0.0.0.0 --port 8000 --reload
