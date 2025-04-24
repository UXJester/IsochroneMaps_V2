"""
Environment Utility Functions
===========================

This module contains utility functions for managing environment variables.

Functions:
    load_env_variables: Load environment variables from a .env file.

Example:
    >>> from src.utils.env_utils import load_env_variables
    >>> dotenv_path, success = load_env_variables()
    >>> print(f"Environment loaded: {success}")
"""

# Standard library imports
import os
import logging
from pathlib import Path
from typing import Tuple, List, Optional

# Third-party imports
from dotenv import load_dotenv

# Local imports
from src.utils.logging_utils import LogContext, with_log_context
from src.utils.error_utils import (
    handle_exception,
    ExceptionContext,
    ConfigMissingError,
    ConfigError,
)


@handle_exception(
    custom_mapping={FileNotFoundError: ConfigError, Exception: ConfigError}
)
@with_log_context(module="env_utils", operation="load_env_variables")
def load_env_variables(required_vars: Optional[List[str]] = None) -> Tuple[Path, bool]:
    """
    Load environment variables from .env file.

    Args:
        required_vars: List of required environment variable names

    Returns:
        Tuple of (dotenv_path, success)

    Raises:
        ConfigError: When .env file could not be loaded
        ConfigMissingError: When required variables are missing
    """
    # Get the project root directory (3 levels up from this file)
    dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"

    with LogContext(file_path=str(dotenv_path)):
        logging.info(f"Loading environment variables from {dotenv_path}")

        # Load the .env file within an exception context
        with ExceptionContext("Loading .env file", ConfigError):
            success = load_dotenv(dotenv_path=dotenv_path)

            if not success:
                logging.warning(f".env file not found at {dotenv_path}")
                return dotenv_path, False

            logging.info(".env file loaded successfully")

        # Check for required variables if specified
        if success and required_vars:
            with LogContext(required_count=len(required_vars)):
                missing_vars = []

                for var in required_vars:
                    with LogContext(variable=var):
                        if not os.environ.get(var):
                            missing_vars.append(var)
                            logging.warning(
                                f"Required environment variable missing: {var}"
                            )

                if missing_vars:
                    missing_vars_str = ", ".join(missing_vars)
                    logging.error(
                        f"Missing required environment variables: {missing_vars_str}"
                    )
                    raise ConfigMissingError(
                        f"Missing required environment variables: {missing_vars_str}"
                    )

                logging.info(
                    f"All required environment variables are present ({len(required_vars)} checked)"
                )

    return dotenv_path, success
