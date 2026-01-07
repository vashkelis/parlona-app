"""Utility functions for interacting with various LLM backends."""

import json
import logging
from typing import Optional, Tuple
from openai import OpenAI
from langdetect import detect

from backend.common.config import Settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified client for different LLM backends."""
    
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize the appropriate LLM client based on configuration."""
        backend = self.settings.llm_backend.lower()
        
        if backend == "openai":
            self.client = OpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url
            )
            self.model = self.settings.openai_model
            logger.info("Initialized OpenAI client with model: %s", self.model)
        elif backend == "vllm":
            self.client = OpenAI(
                api_key=self.settings.vllm_api_key,
                base_url=self.settings.vllm_base_url
            )
            self.model = self.settings.vllm_model
            logger.info("Initialized vLLM client with model: %s", self.model)
        elif backend == "groq":
            self.client = OpenAI(
                api_key=self.settings.groq_api_key,
                base_url=self.settings.groq_base_url
            )
            self.model = self.settings.groq_model
            logger.info("Initialized Groq client with model: %s", self.model)
        elif backend == "ollama":
            self.client = OpenAI(
                api_key="ollama",  # Ollama doesn't require an API key
                base_url=self.settings.ollama_base_url
            )
            self.model = self.settings.ollama_model
            logger.info("Initialized Ollama client with model: %s", self.model)
        else:
            raise ValueError(f"Unsupported LLM backend: {self.settings.llm_backend}")
    
    def detect_language(self, text: str) -> str:
        """Detect the language of the given text."""
        try:
            return detect(text)
        except Exception as e:
            logger.warning("Failed to detect language: %s", e)
            return "en"  # Default to English
    
    def summarize_with_headline(self, transcript: str, max_sentences: int = 4) -> Tuple[str, str, str, str, dict, float]:
        """
        Generate summary, headline, sentiment, and named entities for the given transcript.
        
        Args:
            transcript: The transcript to analyze
            max_sentences: Maximum number of sentences in the summary
            
        Returns:
            Tuple of (summary, headline, detected_language, sentiment_label, entities, sentiment_score)
        """
        if not transcript:
            return "", "No conversation", "en", "neutral", {}, 0.0
        
        # Detect the language of the transcript
        language = self.detect_language(transcript)
        logger.info("Detected language: %s", language)
        
        # Create a prompt that instructs the LLM to generate summary, headline, sentiment, and entities in JSON format
        prompt = f"""
        Please analyze the following conversation and provide a summary, headline, sentiment analysis, and named entities.
        Respond in JSON format with the following fields: "summary", "headline", "sentiment_label", "sentiment_score", and "entities".
        
        Requirements:
        1. The summary should be in {max_sentences} sentences or fewer
        2. All fields should be in the same language as the conversation
        3. The headline should be a single sentence describing the main topic of the call
        4. For sentiment_label, choose one of: "positive", "negative", or "neutral"
        5. For sentiment_score, provide a value between 0.0 and 1.0 (0.0 = very negative, 1.0 = very positive)
        6. For entities, extract all important named entities such as person names, organizations, locations, dates, times, monetary values, etc.
           Format entities as a dictionary where keys are entity types and values are lists of entity values.
           Example: {{"PERSON": ["John Smith", "Mary Johnson"], "ORGANIZATION": ["ABC Company"], "LOCATION": ["New York"]}}
        7. Focus on the key points, main topics, emotional tone, and important entities discussed
        
        Conversation:
        {transcript}
        
        Response format example:
        {{
            "summary": "Summary text here...",
            "headline": "Headline text here...",
            "sentiment_label": "positive|negative|neutral",
            "sentiment_score": 0.8,
            "entities": {{
                "PERSON": ["John Smith"],
                "ORGANIZATION": ["ABC Company"],
                "LOCATION": ["New York"]
            }}
        }}
        """.strip()
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that analyzes conversations and responds in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800,
                response_format={"type": "json_object"}  # Request JSON format response
            )
            
            # Parse the JSON response
            response_text = response.choices[0].message.content.strip()
            logger.debug("LLM response: %s", response_text)
            
            try:
                result = json.loads(response_text)
                summary = result.get("summary", "").strip()
                headline = result.get("headline", "").strip()
                sentiment_label = result.get("sentiment_label", "neutral").strip().lower()
                sentiment_score = float(result.get("sentiment_score", 0.0))
                entities = result.get("entities", {})
                
                # Validate sentiment label
                if sentiment_label not in ["positive", "negative", "neutral"]:
                    sentiment_label = "neutral"
                
                # Validate sentiment score
                if not (0.0 <= sentiment_score <= 1.0):
                    sentiment_score = 0.5
                
                if not summary or not headline:
                    logger.warning("LLM response missing summary or headline: %s", result)
                    raise ValueError("Missing summary or headline in response")
                    
                logger.info("Generated summary: %s", summary)
                logger.info("Generated headline: %s", headline)
                logger.info("Generated sentiment: %s (%.2f)", sentiment_label, sentiment_score)
                logger.info("Extracted entities: %s", entities)
                return summary, headline, language, sentiment_label, entities, sentiment_score
            except json.JSONDecodeError as e:
                logger.error("Failed to parse LLM JSON response: %s", e)
                logger.error("Response text: %s", response_text)
                raise ValueError(f"Invalid JSON response from LLM: {response_text}")
                
        except Exception as e:
            logger.error("Failed to generate summary and headline: %s", e)
            # Return fallback values
            fallback_summary = f"Summary of conversation in {language} (fallback due to error)"
            fallback_headline = f"Conversation in {language} (fallback due to error)"
            return fallback_summary, fallback_headline, language, "neutral", {}, 0.5
    
    def summarize(self, transcript: str, max_sentences: int = 4) -> tuple[str, str]:
        """
        Summarize the given transcript in its original language.
        This is kept for backward compatibility.
        
        Args:
            transcript: The transcript to summarize
            max_sentences: Maximum number of sentences in the summary
            
        Returns:
            Tuple of (summary, detected_language)
        """
        summary, _, language, _, _, _ = self.summarize_with_headline(transcript, max_sentences)
        return summary, language


def get_llm_client(settings: Settings) -> LLMClient:
    """Get a singleton LLM client instance."""
    return LLMClient(settings)