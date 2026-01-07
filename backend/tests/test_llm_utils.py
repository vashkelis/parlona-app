"""Tests for LLM utilities."""

import pytest
from unittest.mock import Mock, patch

from backend.common.config import Settings
from backend.common.llm_utils import LLMClient


def test_llm_client_initialization_openai():
    """Test LLM client initialization with OpenAI backend."""
    settings = Settings(
        llm_backend="openai",
        openai_api_key="test-key",
        openai_base_url="https://api.openai.com/v1",
        openai_model="gpt-4o-mini"
    )
    
    with patch('backend.common.llm_utils.OpenAI') as mock_openai:
        client = LLMClient(settings)
        mock_openai.assert_called_once_with(
            api_key="test-key",
            base_url="https://api.openai.com/v1"
        )
        assert client.model == "gpt-4o-mini"


def test_llm_client_initialization_vllm():
    """Test LLM client initialization with vLLM backend."""
    settings = Settings(
        llm_backend="vllm",
        vllm_api_key="test-key",
        vllm_base_url="http://localhost:8000/v1",
        vllm_model="meta-llama/Meta-Llama-3-8B-Instruct"
    )
    
    with patch('backend.common.llm_utils.OpenAI') as mock_openai:
        client = LLMClient(settings)
        mock_openai.assert_called_once_with(
            api_key="test-key",
            base_url="http://localhost:8000/v1"
        )
        assert client.model == "meta-llama/Meta-Llama-3-8B-Instruct"


def test_llm_client_initialization_groq():
    """Test LLM client initialization with Groq backend."""
    settings = Settings(
        llm_backend="groq",
        groq_api_key="test-key",
        groq_base_url="https://api.groq.com/openai/v1",
        groq_model="llama3-8b-8192"
    )
    
    with patch('backend.common.llm_utils.OpenAI') as mock_openai:
        client = LLMClient(settings)
        mock_openai.assert_called_once_with(
            api_key="test-key",
            base_url="https://api.groq.com/openai/v1"
        )
        assert client.model == "llama3-8b-8192"


def test_llm_client_initialization_ollama():
    """Test LLM client initialization with Ollama backend."""
    settings = Settings(
        llm_backend="ollama",
        ollama_base_url="http://localhost:11434/v1",
        ollama_model="llama3"
    )
    
    with patch('backend.common.llm_utils.OpenAI') as mock_openai:
        client = LLMClient(settings)
        mock_openai.assert_called_once_with(
            api_key="ollama",
            base_url="http://localhost:11434/v1"
        )
        assert client.model == "llama3"


def test_llm_client_unsupported_backend():
    """Test LLM client initialization with unsupported backend."""
    settings = Settings(llm_backend="unsupported")
    
    with pytest.raises(ValueError, match="Unsupported LLM backend: unsupported"):
        LLMClient(settings)


def test_detect_language():
    """Test language detection."""
    settings = Settings(llm_backend="openai", openai_api_key="test-key")
    
    with patch('backend.common.llm_utils.OpenAI'):
        client = LLMClient(settings)
        with patch('backend.common.llm_utils.detect', return_value='en'):
            language = client.detect_language("Hello, world!")
            assert language == 'en'


def test_summarize_success():
    """Test successful summarization."""
    settings = Settings(llm_backend="openai", openai_api_key="test-key")
    
    with patch('backend.common.llm_utils.OpenAI') as mock_openai:
        # Mock the OpenAI client response
        mock_response = Mock()
        mock_response.choices[0].message.content = "This is a summary."
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        
        client = LLMClient(settings)
        summary, language = client.summarize("This is a test transcript.")
        
        assert summary == "This is a summary."
        # Language detection is mocked to return 'en'
        assert language == 'en'


def test_summarize_empty_transcript():
    """Test summarization with empty transcript."""
    settings = Settings(llm_backend="openai", openai_api_key="test-key")
    
    with patch('backend.common.llm_utils.OpenAI'):
        client = LLMClient(settings)
        summary, language = client.summarize("")
        
        assert summary == ""
        assert language == "en"


def test_summarize_failure():
    """Test summarization failure handling."""
    settings = Settings(llm_backend="openai", openai_api_key="test-key")
    
    with patch('backend.common.llm_utils.OpenAI') as mock_openai:
        # Mock the OpenAI client to raise an exception
        mock_openai.return_value.chat.completions.create.side_effect = Exception("API Error")
        
        client = LLMClient(settings)
        with patch('backend.common.llm_utils.detect', return_value='fr'):
            summary, language = client.summarize("Bonjour, monde!")
            
            assert "Summary of conversation in fr" in summary
            assert language == 'fr'