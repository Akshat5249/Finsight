# FinSight — Backend Dockerfile
# Python 3.11-slim base per §4 of the Blueprint.
# Phase 7 (Prompt 24) upgrades to multi-stage + non-root user.

FROM python:3.11-slim

WORKDIR /app

# Install system deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Run with hot-reload for dev; Phase 7 overrides CMD for production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
