#!/bin/bash
#
# vLLM Server - Run on a separate machine with GPU
# Usage: ./docker-vllm.sh [MODEL_NAME] [API_KEY]
#
# Example: ./docker-vllm.sh lmsys/vicuna-7b-v1.5 my-secret-key
#

set -e

MODEL_NAME="${1:-lmsys/vicuna-7b-v1.5}"
API_KEY="${2:-EMPTY}"
PORT="${3:-8000}"

echo "Starting vLLM server..."
echo "  Model: $MODEL_NAME"
echo "  Port: $PORT"

docker run -d \
  --name vllm-server \
  --gpus all \
  -v "${PWD}/models:/models" \
  -p "${PORT}:${PORT}" \
  -p $((PORT+1)):$((PORT+1)) \
  --env TMATE_SESSION_NAME=vllm \
  vllm/vllm-openai:latest \
  --model "${MODEL_NAME}" \
  --api-key "${API_KEY}" \
  --host 0.0.0.0 \
  --port ${PORT} \
  --tensor-parallel-size 1

echo "✅ vLLM server started!"
echo "   Model: ${MODEL_NAME}"
echo "   API URL: http://localhost:${PORT}/v1"
echo "   Check logs: docker logs vllm-server"
echo "   Stop: docker stop vllm-server"
echo ""
echo "To use from other machines, set environment:"
echo "  LLM_BACKEND=vllm"
echo "  VLLM_API_BASE=http://<this-machine-ip>:${PORT}/v1"
echo "  VLLM_API_KEY=${API_KEY}"
echo "  VLLM_MODEL=${MODEL_NAME}"
