# Parlona Core - Community Edition (OSS)

Open-source call analytics pipeline for speech-to-text, summarization, and insights extraction.

## Features

- **Speech-to-Text (STT)**: Powered by faster-whisper with stereo channel diarization
- **Call Summarization**: LLM-powered summaries via OpenAI API
- **Post-processing**: Entity extraction, sentiment analysis, and call insights
- **REST API**: FastAPI-based endpoints for job management and call queries
- **PostgreSQL Storage**: Persistent storage for calls, dialogue turns, and summaries

## Quick Start

### Prerequisites

- Docker & Docker Compose
- An API key (for production use)
- OpenAI API key (optional, for summarization)

### Setup

1. Copy the environment template:
   ```bash
   cp oss/docker/.env.example oss/docker/.env
   ```

2. Edit `.env` with your configuration:
   - Set a strong `CALL_API_KEY` (required for API access)
   - Set `REDIS_PASSWORD` and `POSTGRES_PASSWORD` for security
   - Optionally set `OPENAI_API_KEY` for summarization

3. Start the stack:
   ```bash
   # From repo root:
   docker compose -f oss/docker/docker-compose.yml up --build

   # Or from oss/docker/:
   cd oss/docker && docker compose up --build
   ```

4. Access the API at `http://localhost:8080`

### API Authentication

All API endpoints (except health checks) require the `X-API-Key` header:

```bash
curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8080/v1/calls
```

### Uploading Audio for Processing

```bash
curl -X POST \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "file=@your_audio.wav" \
  http://localhost:8080/v1/jobs/upload
```

## Architecture

```
oss/
├── backend/
│   ├── call_analytics_api/    # FastAPI REST API service
│   ├── stt_service/           # Speech-to-text worker
│   ├── summary_service/       # LLM summarization worker
│   ├── postprocess_service/   # Post-processing worker
│   ├── common/                # Shared utilities
│   ├── migrations/            # Alembic database migrations
│   └── tests/                 # Test suite
└── docker/
    ├── docker-compose.yml     # OSS CE compose file
    └── .env.example           # Environment template
```

## Security Notes

**IMPORTANT**: This is intended for internal/development use. Before exposing publicly:

1. Set strong, unique values for `CALL_API_KEY`, `REDIS_PASSWORD`, and `POSTGRES_PASSWORD`
2. Use HTTPS (configure a reverse proxy like nginx or Traefik)
3. Restrict network access to the API port
4. Consider rate limiting for production deployments

## License

MIT License - see [LICENSE](LICENSE)
