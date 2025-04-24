"""
Database Configuration Module
============================

This module handles Supabase database connectivity, providing standardized
methods for client initialization and connection validation with proper
error handling throughout the application.

Key Components:
-------------
1. Client Initialization:
   - init_supabase(): Creates and initializes the Supabase client
   - get_db_client(): Wrapper function with comprehensive error handling

2. Connection Management:
   - check_db_connection(): Validates database connectivity through a health check

3. Error Handling:
   - Specialized error types for different failure scenarios
   - Consistent logging for all database operations
   - Environment variable validation

Usage:
-----
# Basic database client initialization
from src.config.database import get_db_client
supabase = get_db_client()

# Perform a database health check
from src.config.database import check_db_connection
is_healthy = check_db_connection(supabase)
if not is_healthy:
    print("Database connection issues detected")

# Using with error handling
try:
    supabase = get_db_client()
    if supabase:
        # Perform database operations
        result = supabase.table("my_table").select("*").execute()
except Exception as e:
    print(f"Database error: {e}")

# Direct initialization with custom error handling
from src.config.database import init_supabase
try:
    supabase = init_supabase()
except ConfigError:
    print("Missing environment variables for database connection")
except APIConnectionError:
    print("Could not connect to database API")
except DataAccessError:
    print("General database error occurred")
"""

# Standard library imports
import logging
import os
from typing import Optional

# Third-party imports
from supabase import create_client, Client

# Local imports
from src.utils.logging_utils import with_log_context, LogContext
from src.utils.error_utils import (
    handle_exception,
    ConfigError,
    DataAccessError,
    APIConnectionError,
)


@handle_exception(
    custom_mapping={
        ValueError: ConfigError,
        ConnectionError: APIConnectionError,
        Exception: DataAccessError,
    }
)
@with_log_context(module="database", operation="init_supabase")
def init_supabase() -> Client:
    """
    Initialize and return a Supabase client.

    Returns:
        Client: Initialized Supabase client

    Raises:
        ConfigError: If required environment variables are missing
        APIConnectionError: If connection to Supabase fails
        DataAccessError: For other database-related errors
    """
    # Get Supabase credentials from environment variables
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    # Validate credentials
    if not supabase_url or not supabase_key:
        logging.error("Missing Supabase credentials in environment variables")
        raise ConfigError(
            "Missing required environment variables: SUPABASE_URL and/or SUPABASE_KEY"
        )

    try:
        logging.info("Initializing Supabase client")
        # Create Supabase client
        supabase = create_client(supabase_url, supabase_key)
        logging.info("Supabase client initialized successfully")
        return supabase
    except Exception as e:
        logging.error(f"Failed to initialize Supabase client: {str(e)}")
        raise


@handle_exception(custom_mapping={Exception: DataAccessError})
@with_log_context(module="database", operation="health_check")
def check_db_connection(supabase: Client) -> bool:
    """
    Check if database connection is healthy.

    Args:
        supabase: Supabase client instance

    Returns:
        bool: True if connection is healthy, False otherwise

    Raises:
        DataAccessError: If database health check fails
    """
    try:
        logging.info("Performing database health check")
        # Simple health check by executing a simple query
        response = supabase.table("health_check").select("status").limit(1).execute()

        # Verify that we got a valid response
        if response and hasattr(response, "data"):
            response_data = response.data
            logging.info(f"Database health check response: {response_data}")
            # Log result and return success
            logging.info("Database connection is healthy")
            return True
        else:
            logging.warning("Database health check received invalid response format")
            return False
    except Exception as e:
        logging.warning(f"Database health check failed: {str(e)}")
        return False


def get_db_client() -> Optional[Client]:
    """
    Get Supabase client instance.

    Returns:
        Optional[Client]: Supabase client if successful, None otherwise
    """
    with LogContext(module="database", operation="get_client"):
        try:
            client = init_supabase()
            return client
        except Exception as e:
            logging.error(f"Failed to get database client: {str(e)}")
            return None
