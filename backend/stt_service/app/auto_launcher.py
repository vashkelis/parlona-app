"""Auto-launcher for STT service that detects GPU availability and configures Whisper accordingly."""

import logging
import os
from typing import Dict

logger = logging.getLogger("stt_auto_launcher")


def detect_gpu() -> bool:
    """Detect GPU availability.
    
    Returns:
        bool: True if GPU is available, False otherwise
    """
    # Check for FORCE_CPU environment variable
    if os.environ.get("FORCE_CPU", "").lower() in ("1", "true", "yes"):
        logger.info("CPU mode forced by FORCE_CPU environment variable")
        return False
        
    # Check for STT_ENABLE_GPU environment variable (explicit control)
    stt_enable_gpu = os.environ.get("STT_ENABLE_GPU", "").lower()
    if stt_enable_gpu in ("0", "false", "no"):
        logger.info("GPU disabled by STT_ENABLE_GPU environment variable")
        return False
    elif stt_enable_gpu in ("1", "true", "yes"):
        logger.info("GPU enabled by STT_ENABLE_GPU environment variable")
        # Still need to verify GPU is actually available
        pass  # Continue with normal detection
        
    # Prefer PyTorch if it's already a dependency
    try:
        import torch
        if torch.cuda.is_available():
            logger.info("GPU detected via PyTorch")
            return True
        else:
            logger.info("No GPU detected via PyTorch")
    except Exception:
        logger.debug("PyTorch not available for GPU detection")
        pass

    # Fallback: check for NVIDIA device files
    gpu_available = os.path.exists("/dev/nvidia0")
    if gpu_available:
        logger.info("GPU detected via /dev/nvidia0")
    else:
        logger.info("No GPU detected via /dev/nvidia0")
    return gpu_available

def configure_whisper_from_env() -> None:
    """Configure Whisper environment variables based on GPU availability.
    
    Sets sensible defaults only if env vars are not already set.
    Honors manual overrides via environment variables.
    """
    # Always set WHISPER_MODEL_DIR default if missing
    os.environ.setdefault("WHISPER_MODEL_DIR", "/models/whisper")
    
    # Check if we should force CPU mode
    force_cpu = os.environ.get("FORCE_CPU", "").lower() in ("1", "true", "yes")
    
    # Check if GPU is explicitly disabled
    stt_enable_gpu = os.environ.get("STT_ENABLE_GPU", "").lower()
    gpu_disabled = stt_enable_gpu in ("0", "false", "no")
    
    # Detect GPU if not forced to CPU and not explicitly disabled
    has_gpu = detect_gpu() if not force_cpu and not gpu_disabled else False
    
    if has_gpu:
        logger.info("GPU detected/enabled → using GPU Whisper config")
        # GPU configuration
        os.environ.setdefault("WHISPER_DEVICE", "cuda")
        os.environ.setdefault("WHISPER_COMPUTE_TYPE", "float16")
        os.environ.setdefault("STT_MODEL_NAME", "Systran/faster-whisper-medium")
    else:
        logger.info("No GPU detected/disabled → using CPU Whisper config")
        # CPU configuration
        os.environ.setdefault("WHISPER_DEVICE", "cpu")
        os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8_float32")
        os.environ.setdefault("STT_MODEL_NAME", "Systran/faster-whisper-small")
    
    # Log the final configuration
    logger.info(
        "Whisper configuration - Device: %s, Compute Type: %s, Model: %s, Model Dir: %s",
        os.environ.get("WHISPER_DEVICE"),
        os.environ.get("WHISPER_COMPUTE_TYPE"),
        os.environ.get("STT_MODEL_NAME"),
        os.environ.get("WHISPER_MODEL_DIR"),
    )
def main() -> None:
    """Main entry point for the auto-launcher.
    
    Configures Whisper environment variables and then imports and runs the existing STT worker.
    """
    # Configure Whisper based on environment and GPU detection
    configure_whisper_from_env()
    
    # Import and run the existing STT worker
    from backend.stt_service.app.worker import start_worker
    start_worker()


if __name__ == "__main__":
    # Configure basic logging if not already configured
    if not logging.root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    main()