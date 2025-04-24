"""
Path Utility Functions
===================

This module provides utility functions for path management, project directory navigation,
and filesystem operations commonly needed in Python projects.

Functions:
    add_project_root_to_path: Add the project root directory to Python path to enable proper imports.
    ensure_dirs_exist: Create directories if they don't exist, ensuring paths are available.
    find_project_root: Find the project root directory by looking for marker files.

Typical Usage:
    >>> from src.utils.path_utils import find_project_root, ensure_dirs_exist
    >>> project_root = find_project_root()
    >>> data_dir = project_root / "data"
    >>> output_dir = project_root / "output" / "results"
    >>> ensure_dirs_exist([data_dir, output_dir])
    >>> print(f"Project root: {project_root}")
    >>> print(f"Data directory: {data_dir}")
"""

# Standard library imports
import os
import sys
from pathlib import Path
from typing import List, Optional, Union


def add_project_root_to_path():
    """
    Add the project root directory to Python path.
    This allows for proper imports when scripts are run directly.
    """
    # Get the path to the project root (two levels up from this file)
    project_root = Path(__file__).resolve().parent.parent.parent

    # Add to Python path if not already there
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        return True
    return False


def ensure_dirs_exist(paths: List[Union[str, Path]]) -> None:
    """Ensure that directories exist, creating them if needed.

    Args:
        paths: List of path objects or strings to check/create
    """
    for path in paths:
        os.makedirs(path, exist_ok=True)


def find_project_root(start_dir: Optional[Path] = None) -> Path:
    """
    Find the project root directory by looking for certain marker files.

    Args:
        start_dir: Directory to start searching from (defaults to current file's directory)

    Returns:
        Path to the project root directory

    Raises:
        FileNotFoundError: If project root cannot be determined
    """
    if start_dir is None:
        start_dir = Path(__file__).resolve().parent

    current = start_dir

    # Look up to 5 levels up for project markers
    for _ in range(5):
        # Check for common project root markers
        if (
            (current / ".git").exists()
            or (current / "setup.py").exists()
            or (current / "pyproject.toml").exists()
        ):
            return current

        # Move up one directory
        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent

    # If no markers found, default to 3 levels up from this file
    return Path(__file__).resolve().parent.parent.parent
