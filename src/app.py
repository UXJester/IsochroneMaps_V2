"""
Flask Application Module
=======================

Main application module for the web service, handling route configuration,
middleware setup, error handling, and API endpoint registration.

Key Components:
-------------
1. Application Configuration:
   - Flask app initialization with CORS support
   - Structured logging setup
   - Configuration loading and client initialization

2. Request Middleware:
   - Request ID generation and tracking
   - Lazy-loading of database clients
   - Request/response logging with context

3. Error Handling:
   - Centralized exception handling for all routes
   - Custom error mapping for specific error types
   - Consistent JSON response formatting

4. Core Routes:
   - Static file serving for maps and images
   - Dynamic map generation based on table configuration
   - On-demand isochrone generation using OpenRouteService

5. API Integration:
   - Registration of API blueprint routes
   - Authentication and authorization handling
   - Resource access control

Usage:
-----
# Running the application with Flask
$ flask --app src.app run --debug

# Running with Gunicorn (production)
$ gunicorn 'src.app:app'

# Making requests to dynamic map endpoints
GET /dynamic_maps/centers  # Map showing chapter locations
GET /dynamic_maps/locations  # Map showing member locations with all tile options

# Generating on-demand isochrones
GET /generate_isochrone?lat=42.0&lng=-89.0&time=1800

# Accessing API endpoints
GET /api/data/centers  # Public centers data
GET /api/isochrones  # All isochrone data
"""

# Standard Library Imports
import os
import logging
import uuid
import certifi
import requests

# Third-party Imports
from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS

# Local Imports
from src.utils.logging_utils import setup_structured_logging, LogContext
from src.utils.error_utils import (
    AppError,
    APIError,
    ResourceNotFoundError,
    GeoJSONError,
    DataValidationError,
    ExceptionContext,
    ConfigError,
)
from src.utils.geojson_utils import validate_geojson
from src.routes.api import api_bp
from src.config import IMAGES, MAPS, TABLES
from src.config import get_public_api_tables
from src.config.database import get_db_client
from src.maps import generate_maps

# 1. APPLICATION SETUP
app = Flask(__name__)
CORS(app)
setup_structured_logging(log_file="app.log", level=logging.INFO)
app.config["TABLES"] = None
app.config["SUPABASE_CLIENT"] = None
app.config["ALLOWED_PUBLIC_TABLES"] = get_public_api_tables()


# 2. ERROR HANDLING & MIDDLEWARE
@app.before_request
def before_request():
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    g.request_id = request_id

    # Lazy-load Supabase client on first request
    if app.config["SUPABASE_CLIENT"] is None:
        app.config["SUPABASE_CLIENT"] = get_db_client()
        if app.config["SUPABASE_CLIENT"] is None:
            logging.error("Failed to initialize Supabase client")

    with LogContext(request_id=request_id, path=request.path, method=request.method):
        logging.info(f"Request received: {request.method} {request.path}")


@app.after_request
def after_request(response):
    with LogContext(status_code=response.status_code):
        logging.info(f"Request completed: {response.status_code}")
    return response


@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, AppError):
        if isinstance(e, ResourceNotFoundError):
            status_code = 404
        elif isinstance(e, APIError):
            status_code = 503
        elif isinstance(e, GeoJSONError) or isinstance(e, DataValidationError):
            status_code = 400
        else:
            status_code = 400

        response = {"error": e.__class__.__name__, "message": str(e)}
        logging.error(f"{e.__class__.__name__}: {str(e)}")
    else:
        status_code = 500
        response = {"error": "ServerError", "message": "An unexpected error occurred"}
        logging.error(f"Unhandled exception: {str(e)}", exc_info=True)

    return jsonify(response), status_code


# 3. BASIC UTILITY ROUTES
@app.route("/")
def hello_world():
    """Default route that serves as a basic health check"""
    return send_from_directory(MAPS, "locations.html")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        IMAGES, "favicon.ico", mimetype="image/vnd.microsoft.icon"
    )


# 4. STATIC FILE SERVING
@app.route("/maps/<path:filename>")
def maps(filename):
    """Serve any file from the 'maps' directory"""
    return send_from_directory(MAPS, filename)


# 5. MAP GENERATION ROUTES
@app.route("/dynamic_maps/<string:table_key>")
def dynamic_map(table_key):
    """Dynamically generate and display a map based on table configuration"""
    with LogContext(module="maps", operation=f"dynamic_{table_key}"):
        try:
            # Check if table exists and should generate a map
            if table_key not in TABLES or not TABLES[table_key].get(
                "generate_map", False
            ):
                logging.warning(
                    f"Attempted to generate map for non-mappable table: {table_key}"
                )
                return (
                    jsonify(
                        {
                            "error": "ResourceNotFound",
                            "message": f"Map for '{table_key}' not available",
                        }
                    ),
                    404,
                )

            # Determine if this is a locations map
            include_locations = table_key == "locations"

            # Also add all tile layers for the locations map
            include_all_tiles = table_key == "locations"

            map_object = generate_maps(
                use_local=False,
                include_locations=include_locations,
                return_map_object=True,
                include_all_tiles=include_all_tiles,
            )
            return map_object._repr_html_()
        except Exception as error:
            logging.error(f"Error generating dynamic map for {table_key}: {str(error)}")
            raise


# 6. API SERVICE ROUTES
@app.route("/generate_isochrone", methods=["GET"])
def generate_isochrone():
    """Generate an isochrone using OpenRouteService API"""
    with LogContext(module="isochrone", operation="generate"):
        try:
            # Get parameters from request
            lat = request.args.get("lat")
            lng = request.args.get("lng")
            time = request.args.get(
                "time", "1800"
            )  # Default to 30 minutes (1800 seconds)

            # Validate parameters
            if not lat or not lng:
                logging.warning("Missing lat/lng parameters")
                return jsonify({"error": "Missing required parameters"}), 400

            # Retrieve API key from environment variable
            api_key = os.getenv("ORS_API_KEY")
            if not api_key:
                logging.error("Missing ORS_API_KEY environment variable")
                raise ConfigError("API key not found")

            # Use OpenRouteService API to generate the isochrone
            with ExceptionContext("OpenRouteService API call", APIError):
                url = "https://api.openrouteservice.org/v2/isochrones/driving-car"
                headers = {"Authorization": api_key}
                params = {
                    "locations": [[float(lng), float(lat)]],
                    "range": [int(time)],
                    "smoothing": 25,
                }

                logging.info(f"Calling ORS API for isochrone at ({lat}, {lng})")
                response = requests.post(
                    url, json=params, headers=headers, verify=certifi.where()
                )
                response.raise_for_status()  # Raise an exception for HTTP errors

            # Validate the GeoJSON response
            with ExceptionContext("GeoJSON validation", GeoJSONError):
                geojson_data = response.json()
                validate_geojson(geojson_data)

            logging.info("Isochrone generated successfully")
            return jsonify(geojson_data)

        except Exception as error:
            # Log the error before letting the global error handler deal with it
            logging.error(f"Error generating isochrone: {str(error)}")
            raise


# 7. REGISTER BLUEPRINTS (moved to end)
app.register_blueprint(api_bp, url_prefix="/api")
