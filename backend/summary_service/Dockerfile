FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY oss/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY oss/backend /app/backend

# Add labels for versioning
LABEL org.opencontainers.image.source="https://github.com/parlona/parlonacore"

CMD ["python", "-m", "backend.summary_service.app"]