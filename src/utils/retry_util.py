"""
Retry Utility Functions
===================

This module contains utility functions for retrying operations that might fail transiently.

Functions:
    retry: Retry a function multiple times with exponential backoff between attempts.

Example:
    >>> from src.utils.retry_util import retry
    >>> def fetch_data():
    ...     # Function that might fail transiently
    ...     return api_client.get_data()
    >>> result = retry(fetch_data, retries=3, delay=1)
"""

import logging
import time
from typing import Callable, TypeVar, Optional, Any

from src.utils.logging_utils import with_log_context, LogContext
from src.utils.error_utils import ExceptionContext, APIError

# Define a type variable for the function return type
T = TypeVar("T")


@with_log_context(module="retry_util", operation="retry_operation")
def retry(
    func: Callable[[], T],
    retries: int = 3,
    delay: float = 2,
    error_handler: Optional[Callable[[Exception, int], Any]] = None,
    error_type: type = APIError,
) -> Optional[T]:
    """
    Retry a function multiple times with delay between attempts.

    Args:
        func: Function to retry
        retries: Number of retry attempts
        delay: Delay in seconds between attempts
        error_handler: Optional function to handle errors differently
        error_type: Exception type to raise if all attempts fail

    Returns:
        Result of successful function call

    Raises:
        The specified error_type if all attempts fail
    """
    operation_name = getattr(func, "__name__", "unknown_function")

    with LogContext(operation=operation_name, max_retries=retries, delay=delay):
        for attempt in range(retries):
            try:
                with LogContext(attempt=attempt + 1):
                    logging.info(
                        f"Executing {operation_name} (attempt {attempt + 1}/{retries})"
                    )
                    result = func()
                    logging.info(
                        f"Operation {operation_name} succeeded on attempt {attempt + 1}"
                    )
                    return result

            except Exception as e:
                with LogContext(error=str(e)):
                    logging.warning(f"Attempt {attempt + 1}/{retries} failed: {e}")

                    if error_handler:
                        try:
                            with ExceptionContext(
                                f"Error handler for {operation_name}"
                            ):
                                error_handler(e, attempt)
                        except Exception as handler_error:
                            logging.error(f"Error handler failed: {handler_error}")

                    if attempt < retries - 1:
                        wait_time = delay * (attempt + 1)  # Progressive backoff
                        logging.info(f"Waiting {wait_time} seconds before retry")
                        time.sleep(wait_time)
                    else:
                        logging.error(
                            f"All {retries} attempts for {operation_name} failed"
                        )
                        raise error_type(
                            f"Operation {operation_name} failed after {retries} attempts: {e}"
                        ) from e

        # This code should never be reached due to the exception in the loop
        # but is included for completeness
        return None
