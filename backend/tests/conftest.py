"""pytest configuration for summary service tests."""

import sys
from pathlib import Path

# Add the backend directory to the path so we can import modules
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))