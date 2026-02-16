#!/bin/bash
#
# STT GPU Worker - Run on a separate machine with GPU
# Usage: ./docker-stt-gpu.sh REDIS_HOST REDIS_PASSWORD [STORAGE_DIR]
#
# Example: ./docker-stt-gpu.sh 192.168.1.100 my_secure_password /data
#

set -e

REDIS_HOST="${1?Usage: $0 REDIS_HOST REDIS_PASSWORD [STORAGE_DIR]}"
REDIS_PASSWORD="${2?Usage: $0 REDIS_HOST REDIS_PASSWORD [STORAGE_DIR]}"
STORAGE_DIR="${3:-./storage}"

echo "Starting STT GPU worker..."
echo "  Redis: $REDIS_HOST"
echo "  Storage: $STORAGE_DIR"

docker run -d \
  --name stt-gpu \
  --gpus all \
  -e REDIS_URL="redis://:${REDIS_PASSWORD}@${REDIS_HOST}:6379/0" \
  -e STT_ENABLE_GPU=1 \
  -e WHISPER_DEVICE=cuda \
  -e STT_DIARIZATION_MODE=stereo_channels \
  -e STT_STEREO_SPEAKER_MAPPING=0:agent,1:customer \
  -e WHISPER_LOCAL_ONLY=0 \
  -v "${STORAGE_DIR}:/app/storage" \
  -v "${STORAGE_DIR}/whisper_cache:/models/whisper" \
  --restart unless-stopped \
  parlona/voicecore-stt:1.2.0

echo "✅ STT GPU worker started!"
echo "   Check logs: docker logs stt-gpu"
echo "   Stop: docker stop stt-gpu"
