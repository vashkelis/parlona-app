FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies for PostgreSQL
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY oss/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY oss/backend /app/backend

EXPOSE 8080

# Add labels for versioning
LABEL org.opencontainers.image.source="https://github.com/parlona/parlonacore"

CMD ["uvicorn", "backend.call_analytics_api.app.main:app", "--host", "0.0.0.0", "--port", "8080"]