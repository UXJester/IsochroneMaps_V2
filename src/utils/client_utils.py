"""
Client Utility Functions
=======================

This module contains utility functions for creating and managing API clients.

Functions:
    get_ors_client: Get an initialized OpenRouteService client.
    get_supabase_client: Get an initialized Supabase client.

Example:
    >>> from src.utils.client_utils import get_supabase_client
    >>> client = get_supabase_client
    >>> data = client.table("my_table").select("*").execute()
"""

# Standard library imports
import logging
import os

# Third-party imports
import openrouteservice
from supabase import Client, create_client

# Local imports
from .env_utils import load_env_variables
from .logging_utils import with_log_context, LogContext
from .error_utils import (
    handle_exception,
    ExceptionContext,
    ConfigError,
    APIConnectionError,
)

# Set up initial logging context
with LogContext(module="client_utils"):
    # Load environment variables using the utility
    dotenv_path, env_loaded = load_env_variables()
    if not env_loaded:
        logging.warning(
            f"Environment variables not loaded. .env file not found at {dotenv_path}"
        )


@handle_exception(
    custom_mapping={
        ValueError: ConfigError,
        openrouteservice.exceptions.ApiError: APIConnectionError,
        Exception: APIConnectionError,
    }
)
@with_log_context(module="client_utils", operation="get_ors_client")
def get_ors_client() -> openrouteservice.Client:
    """
    Get OpenRouteService client with API key from environment variable.

    Returns:
        openrouteservice.Client: Initialized ORS client

    Raises:
        ConfigError: When ORS API key is missing
        APIConnectionError: When connection to ORS API fails
    """
    api_key = os.getenv("ORS_API_KEY")

    if not api_key:
        logging.error("ORS API key not found in environment variables")
        raise ConfigError(
            "ORS API key not found. Please set the ORS_API_KEY environment variable in the .env file."
        )

    logging.info("Initializing OpenRouteService client")
    with ExceptionContext("OpenRouteService client initialization", APIConnectionError):
        client = openrouteservice.Client(key=api_key)
        logging.info("OpenRouteService client initialized successfully")
        return client


@handle_exception(
    custom_mapping={
        ValueError: ConfigError,
        ConnectionError: APIConnectionError,
        Exception: APIConnectionError,
    }
)
@with_log_context(module="client_utils", operation="get_supabase_client")
def get_supabase_client() -> Client:
    """
    Get Supabase client with credentials from environment variables.

    Returns:
        Client: Initialized Supabase client

    Raises:
        ConfigError: When Supabase credentials are missing
        APIConnectionError: When connection to Supabase fails
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    # Validate URL
    if not url:
        logging.error("Supabase URL not found in environment variables")
        raise ConfigError(
            "Supabase URL not found. Please set the SUPABASE_URL environment variable in the .env file."
        )

    # Validate key
    if not key:
        logging.error("Supabase key not found in environment variables")
        raise ConfigError(
            "Supabase key not found. Please set the SUPABASE_KEY environment variable in the .env file."
        )

    logging.info("Initializing Supabase client")
    with ExceptionContext("Supabase client initialization", APIConnectionError):
        client = create_client(url, key)
        logging.info("Supabase client initialized successfully")
        return client
