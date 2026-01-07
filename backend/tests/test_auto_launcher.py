"""Tests for the STT auto-launcher module."""

import os
import sys
from unittest.mock import patch, MagicMock

# Add the app directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from auto_launcher import detect_gpu, configure_whisper_from_env


def test_detect_gpu_with_force_cpu():
    """Test that detect_gpu returns False when FORCE_CPU is set."""
    with patch.dict(os.environ, {"FORCE_CPU": "1"}):
        assert detect_gpu() is False


def test_detect_gpu_with_torch_cuda_available():
    """Test that detect_gpu returns True when PyTorch CUDA is available."""
    with patch.dict(os.environ, {}, clear=True):
        with patch('torch.cuda.is_available', return_value=True):
            # Mock the torch import
            mock_torch = MagicMock()
            mock_torch.cuda.is_available.return_value = True
            with patch('builtins.__import__', return_value=mock_torch):
                assert detect_gpu() is True


def test_detect_gpu_with_nvidia_device_file():
    """Test that detect_gpu returns True when NVIDIA device file exists."""
    with patch.dict(os.environ, {}, clear=True):
        with patch('torch.cuda.is_available', return_value=False):
            with patch('os.path.exists', return_value=True):
                # Mock the torch import to raise an exception
                with patch('builtins.__import__', side_effect=ImportError):
                    assert detect_gpu() is True


def test_detect_gpu_without_gpu():
    """Test that detect_gpu returns False when no GPU is available."""
    with patch.dict(os.environ, {}, clear=True):
        with patch('torch.cuda.is_available', return_value=False):
            with patch('os.path.exists', return_value=False):
                # Mock the torch import to raise an exception
                with patch('builtins.__import__', side_effect=ImportError):
                    assert detect_gpu() is False


def test_configure_whisper_from_env_with_gpu():
    """Test that configure_whisper_from_env sets GPU defaults when GPU is available."""
    # Clear relevant environment variables
    for var in ['WHISPER_DEVICE', 'WHISPER_COMPUTE_TYPE', 'STT_MODEL_NAME', 'WHISPER_MODEL_DIR']:
        if var in os.environ:
            del os.environ[var]
    
    with patch('auto_launcher.detect_gpu', return_value=True):
        configure_whisper_from_env()
        
        assert os.environ.get('WHISPER_DEVICE') == 'cuda'
        assert os.environ.get('WHISPER_COMPUTE_TYPE') == 'float16'
        assert os.environ.get('STT_MODEL_NAME') == 'Systran/faster-whisper-medium'
        assert os.environ.get('WHISPER_MODEL_DIR') == '/models/whisper'


def test_configure_whisper_from_env_with_cpu():
    """Test that configure_whisper_from_env sets CPU defaults when no GPU is available."""
    # Clear relevant environment variables
    for var in ['WHISPER_DEVICE', 'WHISPER_COMPUTE_TYPE', 'STT_MODEL_NAME', 'WHISPER_MODEL_DIR']:
        if var in os.environ:
            del os.environ[var]
    
    with patch('auto_launcher.detect_gpu', return_value=False):
        configure_whisper_from_env()
        
        assert os.environ.get('WHISPER_DEVICE') == 'cpu'
        assert os.environ.get('WHISPER_COMPUTE_TYPE') == 'int8_float32'
        assert os.environ.get('STT_MODEL_NAME') == 'Systran/faster-whisper-small'
        assert os.environ.get('WHISPER_MODEL_DIR') == '/models/whisper'


def test_configure_whisper_from_env_preserves_existing_values():
    """Test that configure_whisper_from_env preserves existing environment variables."""
    # Set some existing values
    with patch.dict(os.environ, {
        'WHISPER_DEVICE': 'custom_device',
        'WHISPER_COMPUTE_TYPE': 'custom_compute',
        'STT_MODEL_NAME': 'custom/model',
        'WHISPER_MODEL_DIR': '/custom/model/dir'
    }):
        with patch('auto_launcher.detect_gpu', return_value=True):
            configure_whisper_from_env()
            
            assert os.environ.get('WHISPER_DEVICE') == 'custom_device'
            assert os.environ.get('WHISPER_COMPUTE_TYPE') == 'custom_compute'
            assert os.environ.get('STT_MODEL_NAME') == 'custom/model'
            assert os.environ.get('WHISPER_MODEL_DIR') == '/custom/model/dir'