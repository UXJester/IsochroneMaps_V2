"""
Error Utility Functions
====================

This module contains utility functions and classes for error handling and exceptions.

Classes:
    BaseError: Base class for all custom exceptions.
    ConfigError: Exception raised for configuration errors.
    APIConnectionError: Exception raised for API connection errors.
    DataAccessError: Exception raised for data access errors.
    DataProcessingError: Exception raised for data processing errors.
    DataValidationError: Exception raised for data validation errors.
    GeoJSONError: Exception raised for GeoJSON conversion errors.

Functions:
    handle_exception: Decorator to handle exceptions in functions.
    ExceptionContext: Context manager for handling exceptions.

Example:
    >>> from src.utils.error_utils import handle_exception, DataAccessError
    >>> @handle_exception(custom_mapping={Exception: DataAccessError})
    >>> def load_data():
    ...     # Function that might raise exceptions
    ...     pass
"""

# Standard library imports
import functools
import logging
import traceback
from typing import Type, Callable, TypeVar

# Base exception class
class AppError(Exception):
    """Base exception for all application errors"""

    pass


# Data-related exceptions
class DataError(AppError):
    """Base error related to data operations"""

    pass


class DataAccessError(DataError):
    """Error when accessing data sources (DB, API, etc)"""

    pass


class DataValidationError(DataError):
    """Error when data fails validation"""

    pass


class DataProcessingError(DataError):
    """Error when processing or transforming data"""

    pass


# Configuration-related exceptions
class ConfigError(AppError):
    """Base error related to configuration"""

    pass


class ConfigMissingError(ConfigError):
    """Error when required configuration is missing"""

    pass


# API-related exceptions
class APIError(AppError):
    """Base error for API operations"""

    pass


class APIConnectionError(APIError):
    """Error when connecting to an external API"""

    pass


class APIResponseError(APIError):
    """Error when processing API response"""

    pass


# GeoJSON-related exceptions
class GeoJSONError(AppError):
    """Base error for GeoJSON operations"""

    pass


# Resource errors
class ResourceError(AppError):
    """Base error related to resources"""

    pass


class ResourceNotFoundError(ResourceError):
    """Error when a required resource is not found"""

    pass


# Type variable for function return
T = TypeVar("T")


def handle_exception(
    func: Callable[..., T] = None,
    custom_mapping: dict[Type[Exception], Type[AppError]] = None,
) -> Callable[..., T]:
    """
    Decorator to standardize exception handling.

    Args:
        func: The function to decorate
        custom_mapping: Optional dictionary mapping exceptions to custom app exceptions

    Returns:
        Decorated function with standardized exception handling
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> T:
            try:
                return fn(*args, **kwargs)
            except AppError as e:
                # Already a custom exception, just log and re-raise
                logging.error(f"{e.__class__.__name__}: {str(e)}")
                raise
            except Exception as e:
                # Check for custom mapping
                if custom_mapping and type(e) in custom_mapping:
                    error_cls = custom_mapping[type(e)]
                    logging.error(f"Mapped error in {fn.__name__}: {str(e)}")
                    logging.debug(f"Exception details: {traceback.format_exc()}")
                    raise error_cls(str(e)) from e
                else:
                    # Fall back to generic error
                    logging.error(f"Unexpected error in {fn.__name__}: {str(e)}")
                    logging.debug(f"Exception details: {traceback.format_exc()}")
                    raise AppError(f"Unexpected error: {str(e)}") from e

        return wrapper

    if func is None:
        return decorator
    return decorator(func)


class ExceptionContext:
    """
    Context manager for standardized exception handling.

    Example:
        with ExceptionContext("Operation name", error_cls=DataError):
            # code that might raise exceptions
    """

    def __init__(self, operation_name: str, error_cls: Type[AppError] = AppError):
        self.operation_name = operation_name
        self.error_cls = error_cls

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, exc_val, _exc_tb):
        # Unused parameters (_exc_type, exc_val, _exc_tb) are required by context manager protocol
        if exc_val is None:
            return False  # No exception occurred

        if isinstance(exc_val, AppError):
            # Already a custom exception, just log and let it propagate
            logging.error(
                f"{exc_val.__class__.__name__} in {self.operation_name}: {str(exc_val)}"
            )
            return False  # Don't suppress the exception

        # Convert to custom exception
        logging.error(f"Error in {self.operation_name}: {str(exc_val)}")
        logging.debug(f"Exception details: {traceback.format_exc()}")
        raise self.error_cls(
            f"Error in {self.operation_name}: {str(exc_val)}"
        ) from exc_val


def convert_exception(
    exception: Exception, error_cls: Type[AppError] = AppError, message: str = None
) -> AppError:
    """
    Convert a regular exception to an application-specific exception.

    Args:
        exception: The original exception
        error_cls: The custom exception class to convert to
        message: Optional custom message (uses str(exception) if None)

    Returns:
        An instance of the specified AppError subclass
    """
    msg = message or str(exception)
    return error_cls(msg)
