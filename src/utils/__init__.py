"""
Utilities Module
===============

Central hub for project-wide utility functions with graceful fallbacks and path management.
This module ensures the project root is in the Python path and provides access to all
utility functions across the application.

Key Components:
-------------
1. Path Management:
   - _setup_project_path(): Adds project root to Python path
   - find_project_root(): Locates the project root directory
   - add_project_root_to_path(): Explicit path configuration

2. File System Utilities:
   - ensure_dirs_exist(): Creates directories if they don't exist

3. Environment Management:
   - load_env_variables(): Loads environment variables from .env files

4. Logging Utilities:
   - setup_logging(): Configures basic logging
   - setup_structured_logging(): Configures structured logging with context

5. Client Management:
   - get_supabase_client(): Creates Supabase database client
   - get_ors_client(): Creates OpenRouteService API client

6. Mathematical Utilities:
   - calculate_geographic_midpoint(): Calculates the midpoint of geographic coordinates

Usage:
-----
# Basic imports with guaranteed availability through fallbacks
from src.utils import ensure_dirs_exist, find_project_root

# Create required directories
ensure_dirs_exist(['/path/to/logs', '/path/to/data'])

# Set up logging
from src.utils import setup_logging
setup_logging(log_file_name="application.log")

# Get API clients
from src.utils import get_supabase_client, get_ors_client
db = get_supabase_client()
ors = get_ors_client()

# Calculate geographic center
from src.utils import calculate_geographic_midpoint
lat, lng = calculate_geographic_midpoint([(41.5, -88.0), (42.0, -89.0)])
"""

# Standard library imports
import os
import sys
from pathlib import Path


# Define a function to add project root to the path (but don't call it yet)
def _setup_project_path():
    """Add project root to Python path."""
    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


# Simple utility functions that don't import other modules
def ensure_dirs_exist(paths):
    """Ensure all directories in the list exist."""
    for path in paths:
        os.makedirs(path, exist_ok=True)


# Now add project root to path before importing project modules
_setup_project_path()

# Import only non-decorated utility functions that don't have circular dependencies
# Removing local imports that might cause issues
try:
    from .env_utils import load_env_variables
except ImportError:

    def load_env_variables(required_vars=None):
        """Placeholder for env_utils.load_env_variables"""
        return None, False


try:
    from .logging_utils import setup_logging, setup_structured_logging
except ImportError:

    def setup_logging(log_file_name=None, **kwargs):
        """Placeholder for logging_utils.setup_logging"""
        pass

    def setup_structured_logging(**kwargs):
        """Placeholder for logging_utils.setup_structured_logging"""
        pass


try:
    from .client_utils import get_supabase_client, get_ors_client
except ImportError:

    def get_supabase_client():
        """Placeholder for client_utils.get_supabase_client"""
        return None

    def get_ors_client():
        """Placeholder for client_utils.get_ors_client"""
        return None


try:
    from .path_utils import add_project_root_to_path, find_project_root
except ImportError:

    def add_project_root_to_path():
        """Placeholder for path_utils.add_project_root_to_path"""
        return False

    def find_project_root(start_dir=None):
        """Placeholder for path_utils.find_project_root"""
        return Path(".")


try:
    from .math_utils import calculate_geographic_midpoint
except ImportError:

    def calculate_geographic_midpoint(coords):
        """Placeholder for math_utils.calculate_geographic_midpoint"""
        return (0, 0)


# Define __all__ to control what gets imported with 'from utils import *'
__all__ = [
    # Utility functions
    "ensure_dirs_exist",
    "load_env_variables",
    "setup_logging",
    "setup_structured_logging",
    "get_supabase_client",
    "get_ors_client",
    "add_project_root_to_path",
    "find_project_root",
    "calculate_geographic_midpoint",
]
