"""
Pytest configuration and shared fixtures for agent tests.
"""

import sys
from pathlib import Path

# Add capstone_project to path so we can import modules
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

