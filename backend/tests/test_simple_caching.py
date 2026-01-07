#!/usr/bin/env python3
"""Simple test to verify Whisper model caching configuration."""

import os
from backend.stt_service.app.config import STTServiceSettings


def test_model_caching_config():
    """Test that the model caching configuration is properly loaded."""
    # Test default values
    settings = STTServiceSettings()
    print(f"Default whisper_model_dir: {settings.whisper_model_dir}")
    print(f"Default whisper_local_only: {settings.whisper_local_only}")
    
    assert settings.whisper_model_dir == "/models/whisper"
    assert settings.whisper_local_only is False
    
    print("✓ Default configuration test passed")


if __name__ == "__main__":
    test_model_caching_config()
    print("All tests passed!")