from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings

from backend.common.constants import DEFAULT_JOB_LIST_LIMIT


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL.",
        env="REDIS_URL",
    )
    job_list_limit: int = Field(
        default=DEFAULT_JOB_LIST_LIMIT,
        description="Maximum number of jobs to return when listing.",
        env="JOB_LIST_LIMIT",
    )
    queue_poll_timeout: int = Field(
        default=5,
        description="Seconds for Redis BLPOP timeout in workers.",
        env="QUEUE_POLL_TIMEOUT",
    )
    service_name: str = Field(
        default="call_analytics_api",
        description="Friendly name of the running service for logging.",
        env="SERVICE_NAME",
    )
    storage_dir: str = Field(
        default="/app/storage",
        description="Directory for shared audio/storage assets.",
        env="STORAGE_DIR",
    )
    
    # API Key for authentication
    call_api_key: str = Field(
        default="",
        description="API key for authenticating requests to protected endpoints.",
        env="CALL_API_KEY",
    )
    
    # LLM Configuration
    llm_backend: str = Field(
        default="openai",
        description="LLM backend to use (openai, vllm, groq, ollama)",
        env="LLM_BACKEND",
    )
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key",
        env="OPENAI_API_KEY",
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API base URL",
        env="OPENAI_BASE_URL",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model to use for summarization",
        env="OPENAI_MODEL",
    )
    vllm_host: str = Field(
        default="localhost",
        description="vLLM host",
        env="VLLM_HOST",
    )
    vllm_port: int = Field(
        default=8000,
        description="vLLM port",
        env="VLLM_PORT",
    )
    vllm_base_url: str = Field(
        default="http://localhost:8000/v1",
        description="vLLM API base URL",
        env="VLLM_BASE_URL",
    )
    vllm_model: str = Field(
        default="meta-llama/Meta-Llama-3-8B-Instruct",
        description="vLLM model to use for summarization",
        env="VLLM_MODEL",
    )
    vllm_api_key: str = Field(
        default="EMPTY",
        description="vLLM API key",
        env="VLLM_API_KEY",
    )
    groq_api_key: str = Field(
        default="",
        description="Groq API key",
        env="GROQ_API_KEY",
    )
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        description="Groq API base URL",
        env="GROQ_BASE_URL",
    )
    groq_model: str = Field(
        default="llama3-8b-8192",
        description="Groq model to use for summarization",
        env="GROQ_MODEL",
    )
    ollama_host: str = Field(
        default="localhost",
        description="Ollama host",
        env="OLLAMA_HOST",
    )
    ollama_port: int = Field(
        default=11434,
        description="Ollama port",
        env="OLLAMA_PORT",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434/v1",
        description="Ollama API base URL",
        env="OLLAMA_BASE_URL",
    )
    ollama_model: str = Field(
        default="llama3",
        description="Ollama model to use for summarization",
        env="OLLAMA_MODEL",
    )

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    # Validate that CALL_API_KEY is set
    settings = Settings()
    if not settings.call_api_key:
        raise RuntimeError("CALL_API_KEY is not set. Please check your .env file.")
    return settings