"""
Logging Utility Functions
======================

This module contains utility functions and classes for logging.

Classes:
    LogContext: Context manager for adding contextual information to logs.

Functions:
    configure_logging: Configure the logging system with specified parameters.
    with_log_context: Decorator to add logging context to functions.

Example:
    >>> from src.utils.logging_utils import configure_logging, LogContext
    >>> configure_logging(level="INFO")
    >>> with LogContext(module="my_module"):
    ...     logging.info("This log has context")
"""

# Standard library imports
import logging
import os
import uuid
from pathlib import Path
from typing import Optional
from functools import wraps


class LogContext:
    """
    Context manager for adding structured context to logs.

    Example:
        with LogContext(module="data_utils", operation="load_data"):
            logging.info("Loading data")
    """

    def __init__(self, **kwargs):
        self.old_context = getattr(logging, "context", {})
        self.context = {**self.old_context, **kwargs}

    def __enter__(self):
        logging.context = self.context
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        # Unused parameters (_exc_type, _exc_val, _exc_tb) are required by context manager protocol
        logging.context = self.old_context
        # No exception handling here, returning None (or False) to propagate exceptions


class ContextAwareFormatter(logging.Formatter):
    """
    Custom formatter that includes context information in log records.

    This formatter adds any context from the LogContext to each log message.
    """

    def format(self, record):
        # Add context attributes to the record
        context = getattr(logging, "context", {})
        for key, value in context.items():
            if not hasattr(record, key):
                setattr(record, key, value)

        # Ensure request_id is always available to avoid formatting errors
        if not hasattr(record, "request_id"):
            setattr(record, "request_id", "-")

        return super().format(record)


def with_log_context(func=None, **context_kwargs):
    """
    Decorator to add context to all log messages within a function.

    Args:
        func: The function to decorate
        **context_kwargs: Context values to add to log messages

    Example:
        @with_log_context(module="auth")
        def authenticate_user(username):
            logging.info(f"Authenticating {username}")  # Will include module="auth"
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            with LogContext(**context_kwargs):
                return f(*args, **kwargs)

        return wrapped

    if func is None:
        return decorator
    return decorator(func)


def get_request_id() -> str:
    """Generate a unique request ID for tracing."""
    return str(uuid.uuid4())


def clear_log_context():
    """Clear all context values from the logging context."""
    if hasattr(logging, "context"):
        delattr(logging, "context")


# Logging configuration
def setup_logging(
    log_file_name=None,
    logs_dir=None,
    level=logging.INFO,
    format_string="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    add_request_id=False,
    request_id=None,
):
    """Set up logging configuration.

    Args:
        log_file_name: Name of the log file
        logs_dir: Path to logs directory (optional)
        level: Logging level (default: INFO)
        format_string: Format string for log messages
        add_request_id: Whether to add a request_id to the logging context
        request_id: Custom request ID (if None and add_request_id=True, one will be generated)
    """
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create context-aware formatter
    formatter = ContextAwareFormatter(format_string)

    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # If a log file is specified, add a file handler
    if log_file_name:
        try:
            if not logs_dir:
                # Use a default logs directory if none provided
                logs_dir = Path(__file__).resolve().parent.parent.parent / "logs"

            # Create logs directory if it doesn't exist
            os.makedirs(logs_dir, exist_ok=True)

            # Create and add file handler
            log_file_path = Path(logs_dir) / log_file_name
            file_handler = logging.FileHandler(log_file_path)
            file_handler.setFormatter(formatter)

            # Add the handler to the root logger
            root_logger.addHandler(file_handler)

            logging.info(f"Logging to file: {log_file_path}")
        except Exception as e:
            logging.error(f"Failed to setup file logging: {e}")

    # Set default empty context
    logging.context = {}

    # Add request_id to context if needed
    if add_request_id:
        request_id = request_id or get_request_id()
        with LogContext(request_id=request_id):
            logging.info("Logging system initialized with request ID")
    else:
        logging.info("Logging system initialized")


def setup_structured_logging(
    log_file: Optional[str] = None,
    logs_dir: Optional[str] = None,
    level: int = logging.INFO,
    format_string: str = "%(asctime)s - %(levelname)s - %(name)s - %(request_id)s - %(message)s",
    request_id: Optional[str] = None,
):
    """
    Configure structured logging with context awareness and request ID tracking.
    This is a convenience wrapper around setup_logging with structured logging defaults.

    Args:
        log_file: Optional name of log file
        logs_dir: Optional path to logs directory
        level: Logging level
        format_string: Format string for log messages
        request_id: Optional custom request ID (generated if None)
    """
    # Use the enhanced setup_logging with request ID enabled
    setup_logging(
        log_file_name=log_file,
        logs_dir=logs_dir,
        level=level,
        format_string=format_string,
        add_request_id=True,
        request_id=request_id,
    )
