"""
Configuration Module
===================

Central configuration for the project defining paths, map settings,
and database/file structures required across the application.

Key Components:
--------------
1. Base Paths:
   - ROOT: Project root directory
   - LOGS: Directory for application logs
   - DATA: Directory for data storage
   - ISOCHRONES: Directory for isochrone GeoJSON files
   - LOCATIONS: Directory for location CSV files
   - MAPS: Directory for generated HTML maps
   - STATIC: Directory for static assets (CSS, JS, images)

2. Map Settings (MAP_SETTINGS):
   - zoom: Default map zoom level
   - min_zoom/max_zoom: Zoom restrictions
   - layers: Layer configuration for each map component
   - colors: Color palette for map features
   - tiles: Tile provider configuration with preferred formats

3. Table Configurations (TABLES):
   - Schema definitions for database tables and related CSV files
   - Field mappings between database and application
   - Metadata for each table type (geocoding needs, API visibility)

Usage:
-----
# Import configuration variables
from src.config import ROOT, DATA, MAP_SETTINGS, TABLES

# Access map configuration
default_zoom = MAP_SETTINGS["zoom"]
isochrone_color = MAP_SETTINGS["colors"][0]

# Get a table's column mapping
chapter_name_field = TABLES["centers"]["columns"]["name"]

# Check if a table needs geocoding
needs_geocoding = TABLES["locations"]["needs_geocoding"]

# Get path to a data file
from pathlib import Path
centers_file = Path(LOCATIONS, "geocoded_chapters.csv")

# Get public API tables
from src.config import get_public_api_tables
public_tables = get_public_api_tables()
"""

# Standard library imports
from pathlib import Path

# Local imports
from src.utils.path_utils import ensure_dirs_exist

# Define base paths
ROOT = Path(__file__).resolve().parent.parent.parent
LOGS = Path(ROOT, "logs")
DATA = Path(ROOT, "data")
ISOCHRONES = Path(DATA, "isochrones")
LOCATIONS = Path(DATA, "locations")
MAPS = Path(ROOT, "maps")
STATIC = Path(ROOT, "src", "static")
CSS = Path(STATIC, "css")
JS = Path(STATIC, "js")
IMAGES = Path(STATIC, "images")

# Define Map settings
MAP_SETTINGS = {
    "zoom": 8,
    "min_zoom": 5,
    "max_zoom": 12,
    "layers": {
        "draw": {"name": "Draw Layer", "show": True},
        "isochrones": {"name": "Isochrones", "show": True},
        "centers": {"name": "City Centers", "show": True},
        "locations": {
            "name": "Points of Interest",
            "show": False,
        },  # Will be overridden for locations map
    },
    "tiles": {
        "default": "OpenStreetMap",  # Default tile set to use
        "preferred": "CartoDB",  # Preferred tile set to use
        "providers": {
            "OpenStreetMap": {"name": "OpenStreetMap"},
            "CartoDB": {"name": "CartoDB positron"},
            "Satellite": {
                "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                "attr": "Esri",
                "name": "Satellite",
            },
            "Dark": {"name": "CartoDB dark_matter"},
            "Topographic": {"name": "OpenTopoMap"},
        },
    },
    "colors": [
        # Primary colors for isochrones
        "#3366CC",  # Blue
        "#DC3912",  # Red
        "#FF9900",  # Orange
        "#109618",  # Green
        "#990099",  # Purple
        "#0099C6",  # Teal
        # Secondary colors for isochrones
        "#DD4477",  # Pink
        "#66AA00",  # Lime
        "#B82E2E",  # Dark Red
        "#316395",  # Dark Blue
        "#994499",  # Violet
        "#22AA99",  # Sea Green
        "#AAAA11",  # Olive
        # Complementary colors for isochrones
        "#69C",  # Light Blue
        "#F90",  # Amber
        "#9C6",  # Light Green
        "#C69",  # Magenta
        "#996",  # Olive Green
        "#669",  # Lavender
        "#6CC",  # Light Teal
        "#C96",  # Gold
        "#C66",  # Rust
        "#6A0",  # Dark Lime
        "#969",  # Plum
        "#969",  # Slate
    ],
}

# Reserved for future use
MODES = {
    "use-local": {},
    "use-db": {},
}

# Define Table Configurations
TABLES = {
    "centers": {
        "table_name": "city_centers",
        "needs_geocoding": True,
        "public_api_visible": True,
        "generate_map": True,
        "columns": {
            "id": "id",
            "address": "address",
            "city": "city",
            "state": "state",
            "zip_code": "zip_code",
            "latitude": "latitude",
            "longitude": "longitude",
        },
    },
    "locations": {
        "table_name": "locations",
        "needs_geocoding": True,
        "public_api_visible": True,
        "generate_map": True,
        "columns": {
            "id": "id",
            "name": "name",
            "address": "address",
            "city": "city",
            "state": "state",
            "zip_code": "zip_code",
            "latitude": "latitude",
            "longitude": "longitude",
        },
    },
    "isochrones": {
        "table_name": "isochrones",
        "needs_geocoding": False,  # This table doesn't need geocoding
        "public_api_visible": True,
        "generate_map": False,
        "columns": {
            "id": "id",
            "name": "name",
            "state": "state",
            "zip_code": "zip_code",
            "group_index": "group_index",
            "value": "value",
            "center": "center",
            "geometry": "geometry",
            "metadata": "metadata",
        },
    },
    "health_check": {
        "table_name": "health_check",
        "needs_geocoding": False,
        "public_api_visible": True,
        "generate_map": False,
        "columns": {
            "id": "id",
            "status": "status",
            "timestamp": "timestamp",
            "message": "message",
        },
    },
}


# Helper function to get list of public API tables
def get_public_api_tables():
    return [
        config["table_name"]
        for _, config in TABLES.items()
        if config.get("public_api_visible", False)
    ]


# Ensure directories exist
directories_to_ensure = [DATA, LOGS, MAPS, IMAGES, ISOCHRONES, LOCATIONS]
ensure_dirs_exist(directories_to_ensure)
