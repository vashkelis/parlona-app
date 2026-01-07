FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# 1) System dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libsndfile1 \
    portaudio19-dev \
    libasound2-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 2) Install Python dependencies in two steps to leverage Docker layer caching
COPY oss/backend/requirements.txt /tmp/requirements.txt

# First install binary-heavy deps
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        numpy==1.26.4 \
        soundfile==0.12.1 \
        resampy==0.4.2

# Then install the rest
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 3) Copy application code
COPY oss/backend /app/backend

# Add labels for versioning
LABEL org.opencontainers.image.source="https://github.com/parlona/parlonacore"

CMD ["python", "-m", "backend.stt_service.app.auto_launcher"]