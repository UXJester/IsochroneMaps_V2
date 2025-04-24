"""
API Routes Module
================

This module defines Flask Blueprint routes for the application's REST API,
providing data access endpoints and visualization services with standardized
error handling and logging.

Key Components:
-------------
1. Generic Data Access:
   - /data/<table_name>: Paginated access to database tables
   - Security validation against allowed public tables
   - Consistent error handling and response formatting

2. Specialized Data Endpoints:
   - /isochrones: Access to isochrone GeoJSON data
   - Optimized for map visualization

3. Visualization Endpoints:
   - /maps/<table_key>: Dynamic Folium map generation
   - Supports different map types based on table configuration

4. Security & Error Handling:
   - Request validation and table access restrictions
   - Consistent error responses with appropriate HTTP status codes
   - Comprehensive logging with request context

Usage:
-----
# Accessing data with pagination
GET /api/data/centers?page=1&page_size=20

# Retrieving GeoJSON isochrones for all centers
GET /api/isochrones

# Generating a dynamic map for centers
GET /api/maps/centers

# Generating a dynamic map for locations (with locations enabled)
GET /api/maps/locations

Error Handling:
-------------
- 400: Bad Request (invalid parameters)
- 404: Resource not found (table doesn't exist or isn't public)
- 500: Server error (database connection issues)

All API responses include appropriate status codes and JSON error messages.
"""

# Standard Library Imports
import logging

# Third-party Imports
from flask import Blueprint, jsonify, request, current_app, g

# Local Imports
from src.utils.logging_utils import LogContext, with_log_context
from src.utils.error_utils import (
    handle_exception,
    ExceptionContext,
    DataAccessError,
    APIError,
    ResourceNotFoundError,
    DataValidationError,
    ConfigError,
)
from src.utils.data_utils import load_isochrones
from src.maps import generate_maps
from src.config import TABLES

api_bp = Blueprint("api", __name__)

# --------------------------------------
# GENERIC DATA ACCESS ENDPOINTS
# --------------------------------------


@api_bp.route("/data/<string:table_name>", methods=["GET"])
@with_log_context(module="api", endpoint="get_data")
@handle_exception(
    custom_mapping={ValueError: DataValidationError, Exception: DataAccessError}
)
def get_data(table_name):
    """
    Generic endpoint to fetch data from a specified table.
    """
    logging.info(f"Fetching data from table: {table_name}")

    # Get the Supabase client from app config
    supabase = current_app.config.get("SUPABASE_CLIENT")
    if not supabase:
        raise ConfigError("Supabase client not configured")

    # Validate table name for security - using the ALLOWED_PUBLIC_TABLES from config
    allowed_tables = current_app.config.get("ALLOWED_PUBLIC_TABLES", [])
    if table_name not in allowed_tables:
        logging.warning(f"Attempted access to unauthorized table: {table_name}")
        raise ResourceNotFoundError(f"Table '{table_name}' not found or not accessible")

    # Execute query with pagination
    page = request.args.get("page", default=1, type=int)
    page_size = request.args.get("page_size", default=100, type=int)

    with LogContext(page=page, page_size=page_size):
        logging.debug(f"Pagination: page={page}, page_size={page_size}")

        # Use ExceptionContext for database operations
        with ExceptionContext(f"Querying data from {table_name}", APIError):
            response = (
                supabase.table(table_name)
                .select("*")
                .range((page - 1) * page_size, page * page_size - 1)
                .execute()
            )

            response_data = response.data if hasattr(response, "data") else []
            data_count = len(response_data)

        if not response_data:
            logging.info(f"No data found in table: {table_name}")
            return jsonify({"data": [], "count": 0})

        logging.info(f"Successfully retrieved {data_count} rows from {table_name}")
        return jsonify({"data": response_data, "count": data_count})


# --------------------------------------
# SPECIALIZED DATA ENDPOINTS
# --------------------------------------


@api_bp.route("/isochrones", methods=["GET"])
@with_log_context(module="api", endpoint="get_isochrones")
@handle_exception(custom_mapping={Exception: DataAccessError})
def get_isochrones():
    """
    Endpoint to return isochrone data.
    """
    request_id = getattr(g, "request_id", "unknown")
    with LogContext(request_id=request_id):
        logging.info("Fetching isochrones data")

        # Get the Supabase client from app config
        supabase = current_app.config.get("SUPABASE_CLIENT")
        if not supabase:
            raise ConfigError("Supabase client not configured")

        # Get the tables configuration
        tables_config = current_app.config.get("TABLES", {})
        if not tables_config:
            raise ConfigError("Tables configuration not found")

        # Use ExceptionContext for the database operation
        with ExceptionContext("Loading isochrones from database", APIError):
            # Load isochrone data using the enhanced load_isochrones function
            isochrones = load_isochrones(supabase, tables_config)
            feature_count = len(isochrones.get("features", []))

        logging.info(f"Successfully retrieved {feature_count} isochrone features")
        return jsonify(isochrones)


# --------------------------------------
# VISUALIZATION ENDPOINTS
# --------------------------------------


@api_bp.route("/maps/<string:table_key>", methods=["GET"])
@with_log_context(module="api", endpoint="get_map")
@handle_exception(custom_mapping={Exception: DataAccessError})
def get_map(table_key):
    """
    Dynamic endpoint to return maps for tables with generate_map=True.
    """
    request_id = getattr(g, "request_id", "unknown")
    with LogContext(request_id=request_id):
        # Check if table exists and should generate a map
        if table_key not in TABLES or not TABLES[table_key].get("generate_map", False):
            logging.warning(
                f"Attempted to generate map for non-mappable table: {table_key}"
            )
            raise ResourceNotFoundError(f"Map for '{table_key}' not available")

        logging.info(f"Generating map for: {table_key}")

        # Determine if this is a locations map
        include_locations = table_key == "locations"

        map_object = generate_maps(
            use_local=False, include_locations=include_locations, return_map_object=True
        )

        return map_object._repr_html_()
