"""
Map Generation Module
====================

This module generates interactive Folium maps for visualizing centers and isochrones
with optional location markers. It supports both database-backed and file-based workflows,
enabling deployment in various environments.

Key Features:
-----------
* Two operating modes:
  - Database mode ('use-db'): Reads from Supabase for dynamic map generation
  - Local mode ('use-local'): Uses local CSV/GeoJSON files for static HTML maps
* Interactive layers:
  - Isochrone polygons with travel time visualization (sorted by size)
  - Center markers with popups and tooltips
  - Optional location markers
  - Drawing tools for user annotations
* Multiple tile provider support:
  - Configurable default and preferred providers
  - Support for standard Folium providers and custom tile URLs
  - Option to include all available tile layers with layer switcher
* Map optimization with CSS/JS minification
* Comprehensive error handling and structured logging
* Configuration-driven approach using MAP_SETTINGS

Main Functions:
-------------
* generate_maps: Generate map files with different configurations
* create_map: Create a Folium map with layers and features
* load_data_local: Load data from local files
* load_isochrones_local: Load isochrone data from local GeoJSON files
* minify_html: Optimize generated HTML files
* validate_map_config: Ensure map configuration is valid

Command-line Usage:
-----------------
# Generate static HTML maps from local files (default mode)
$ python -m src.maps --mode use-local

# Generate maps with specific tile provider
$ python -m src.maps --mode use-local --tile-provider Satellite

# Configure for dynamic Flask serving with database
$ python -m src.maps --mode use-db

Code Examples:
------------
# Generate static maps from local files
from src.maps import generate_maps
maps = generate_maps(use_local=True)

# Create a dynamic map for web serving
from src.maps import generate_maps
map_obj = generate_maps(
    use_local=False,  # Use database
    include_locations=True,  # Include location markers
    return_map_object=True,  # Return Folium map object instead of file paths
    tile_provider="CartoDB",  # Use CartoDB as the tile provider
    include_all_tiles=True   # Include all tile providers as options
)

Configuration:
------------
The module uses MAP_SETTINGS from src.config to control map appearance:
- zoom: Default map zoom level
- min_zoom/max_zoom: Zoom restrictions
- colors: List of colors for isochrones
- layers: Configuration for map layers
- tiles: Tile provider configuration

Dependencies:
-----------
* Folium for map generation
* pandas for data processing
* Supabase client (in database mode)
* htmlmin, csscompressor and jsmin for optimizing output
"""

# Standard Library Imports
import os
import sys
import logging
import re
import json
from pathlib import Path
import argparse

# Add the project root to the Python path before other project imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Third-party Imports
import folium
import htmlmin
import pandas as pd
from csscompressor import compress
from folium import MacroElement
from folium.plugins import Draw
from jinja2 import Template
from jsmin import jsmin

# Local Imports
from src.utils.logging_utils import (
    setup_structured_logging,
    with_log_context,
    LogContext,
)
from src.utils.data_utils import load_data, load_isochrones
from src.utils.math_utils import calculate_geographic_midpoint
from src.utils.client_utils import get_supabase_client
from src.utils.error_utils import (
    handle_exception,
    DataAccessError,
    GeoJSONError,
    ConfigError,
)


from src.config import CSS, JS, MAPS, DATA, TABLES, MAP_SETTINGS

# Configure logging with structured logging
setup_structured_logging(log_file="maps.log")


@handle_exception(custom_mapping={ValueError: DataAccessError, Exception: GeoJSONError})
@with_log_context(module="maps", operation="generate")
def generate_maps(
    use_local=False,
    include_locations=False,
    return_map_object=False,
    tile_provider=None,
    include_all_tiles=False,
):
    """Generate map files with structured logging and error handling.

    Args:
        use_local (bool): Whether to use local files instead of database
        include_locations (bool): Whether to include location markers on the map
        return_map_object (bool): If True, returns the Folium map object instead of file paths
                                 (used for dynamic Flask endpoints)
        tile_provider (str): Optional name of the tile provider to use

    Returns:
        dict or folium.Map: Either file paths to generated maps or a Folium map object
    """

    if use_local:
        # Load data from local files
        with LogContext(action="load_local_data"):
            logging.info("Loading data from local files")
            centers_df = load_data_local("centers")
            locations_df = load_data_local("locations")
            isochrones_df = load_isochrones_local()
    else:
        # Initialize Supabase client and load from database
        with LogContext(action="initialize_client"):
            logging.info("Initializing Supabase client")
            supabase = get_supabase_client()
            if not supabase:
                raise DataAccessError("Failed to initialize Supabase client")

        # Load data using the load_data function
        with LogContext(action="load_data"):
            logging.info("Loading data from Supabase")
            centers_df = load_data(supabase, TABLES["centers"]["table_name"])
            locations_df = load_data(supabase, TABLES["locations"]["table_name"])
            isochrones_df = load_isochrones(supabase, TABLES)

    # Ensure data is valid
    with LogContext(action="validate_data"):
        logging.info("Validating loaded data")
        if centers_df.empty:
            raise DataAccessError("Center data is empty.")
        if locations_df.empty:
            raise DataAccessError("Location data is empty.")
        if not isochrones_df["features"]:
            raise DataAccessError("Isochrone data is empty.")

    # Extract valid coordinates from the Centers DataFrame
    with LogContext(action="calculate_midpoint"):
        if "latitude" in centers_df.columns and "longitude" in centers_df.columns:
            center_coords = centers_df.dropna(subset=["latitude", "longitude"])
            if center_coords.empty:
                raise DataAccessError("No valid Center coordinates found.")
            coords = list(zip(center_coords["latitude"], center_coords["longitude"]))
            map_center = calculate_geographic_midpoint(coords)
        else:
            raise DataAccessError(
                "Centers data must contain 'latitude' and 'longitude' columns."
            )

    # Create a dictionary to map feature names to colors
    feature_colors = {}
    features = {
        feature["properties"].get("name", "Unknown")
        for feature in isochrones_df["features"]
    }
    for idx, name in enumerate(features):
        feature_colors[name] = MAP_SETTINGS["colors"][idx % len(MAP_SETTINGS["colors"])]

    # Create and return the requested map for dynamic serving
    if return_map_object:
        with LogContext(action="create_dynamic_map"):
            logging.info(
                f"Creating dynamic map with locations={include_locations}, tile_provider={tile_provider}"
            )
            dynamic_map = create_map(
                center_coords,
                isochrones_df,
                feature_colors,
                map_center,
                include_locations=include_locations,
                locations_df=locations_df if include_locations else None,
                tile_provider=tile_provider,
                include_all_tiles=include_all_tiles,
            )
            return dynamic_map

    # Generate static HTML map files
    with LogContext(action="create_maps"):
        # Create maps directory check
        maps_path = Path(MAPS)
        maps_path.mkdir(parents=True, exist_ok=True)

        # Get table names from configuration for file naming
        centers_table_name = TABLES["centers"].get("table_name", "centers")
        locations_table_name = TABLES["locations"].get("table_name", "locations")

        # Generate the map without locations
        centers_map = Path(maps_path, f"{centers_table_name}.html")
        logging.info(f"Creating map without locations as {centers_table_name}.html")
        without_locations = create_map(
            center_coords,
            isochrones_df,
            feature_colors,
            map_center,
            include_locations=False,
            locations_df=None,
            tile_provider=tile_provider,
        )
        without_locations.save(str(centers_map))
        minify_html(centers_map)
        logging.info("Map without locations saved to: %s", centers_map)

        # Generate the map with locations
        locations_map = Path(maps_path, f"{locations_table_name}.html")
        logging.info(f"Creating map with locations as {locations_table_name}.html")
        with_locations = create_map(
            center_coords,
            isochrones_df,
            feature_colors,
            map_center,
            include_locations=True,
            locations_df=locations_df,
            tile_provider=tile_provider,
            include_all_tiles=True,  # Include all tile providers as additional layers
        )
        with_locations.save(str(locations_map))
        minify_html(locations_map)
        logging.info("Map with locations saved to: %s", locations_map)

    return {"centers_map": str(centers_map), "locations_map": str(locations_map)}


# Create a map with the specified layers and features
# This function is used in both static and dynamic map generation
def create_map(
    center_coords,
    isochrones_df,
    feature_colors,
    map_center,
    include_locations=False,
    locations_df=None,
    tile_provider=None,
    include_all_tiles=False,
):
    """Create a map with the specified layers and features.

    Args:
        center_coords: DataFrame containing center coordinates
        isochrones_df: GeoJSON data for isochrones
        feature_colors: Dictionary mapping feature names to colors
        map_center: Center coordinates for the map [lat, lng]
        include_locations: Whether to include location markers
        locations_df: DataFrame containing location data
        tile_provider: Optional override for map tile provider
        include_all_tiles: Whether to include all tile providers as additional layers

    Returns:
        folium.Map: The generated map object
    """
    logging.info("Creating map with center at %s", str(map_center))

    # Get tiles configuration from settings
    tiles_config = MAP_SETTINGS.get("tiles", {})
    providers = tiles_config.get(
        "providers", {"OpenStreetMap": {"name": "OpenStreetMap"}}
    )

    # Use specified provider, or default from config, or fallback to OpenStreetMap
    provider_name = tile_provider or tiles_config.get("default", "OpenStreetMap")
    provider = providers.get(
        provider_name, providers.get("OpenStreetMap", {"name": "OpenStreetMap"})
    )

    # Log the selected tile provider
    logging.info(f"Using map tile provider: {provider_name}")

    # Create the map with selected tile provider and zoom level from configuration
    if "tiles" in provider:
        # Custom tiles URL provided
        m = folium.Map(
            location=map_center,
            zoom_start=MAP_SETTINGS.get("zoom", 10),
            min_zoom=MAP_SETTINGS.get("min_zoom", 5),
            max_zoom=MAP_SETTINGS.get("max_zoom", 12),
            control_scale=True,
            tiles=None,  # No default tiles
        )

        # Add the custom tile layer
        folium.TileLayer(
            tiles=provider["tiles"],
            attr=provider.get("attr", ""),
            name=provider.get("name", provider_name),
        ).add_to(m)
    else:
        # Standard folium tile provider
        m = folium.Map(
            location=map_center,
            zoom_start=MAP_SETTINGS.get("zoom", 10),
            min_zoom=MAP_SETTINGS.get("min_zoom", 5),
            max_zoom=MAP_SETTINGS.get("max_zoom", 12),
            control_scale=True,
            tiles=provider.get("name", "OpenStreetMap"),
        )

    # Optionally add additional tile layers that users can switch between
    if include_all_tiles:
        tiles_config = MAP_SETTINGS.get("tiles", {})
        providers = tiles_config.get("providers", {})

        # Use CartoDB as the preferred provider by default, or get from config
        preferred_provider = tiles_config.get("preferred", "CartoDB")

        # First, process all non-preferred providers
        for name, provider_config in providers.items():
            # Skip both the already added provider and the preferred provider
            if (
                (tile_provider and name == tile_provider)
                or (not tile_provider and name == tiles_config.get("default"))
                or name == preferred_provider
            ):
                continue

            # Process non-preferred providers as before
            provider_name = provider_config.get("name", name)
            try:
                # Try adding the tile layer with minimal parameters
                folium.TileLayer(
                    tiles=provider_name,
                    name=name,
                ).add_to(m)
            except ValueError:
                # If that fails, provide attribution
                folium.TileLayer(
                    tiles=provider_config.get("tiles", provider_name),
                    attr=provider_config.get("attr", "© Map contributors"),
                    name=name,
                ).add_to(m)

        # Finally add the preferred provider last so it becomes active
        if preferred_provider in providers and not (
            (tile_provider and preferred_provider == tile_provider)
            or (not tile_provider and preferred_provider == tiles_config.get("default"))
        ):
            provider_config = providers.get(preferred_provider, {})
            provider_name = provider_config.get("name", preferred_provider)

            try:
                folium.TileLayer(
                    tiles=provider_name,
                    name=preferred_provider,
                ).add_to(m)
            except ValueError:
                folium.TileLayer(
                    tiles=provider_config.get("tiles", provider_name),
                    attr=provider_config.get("attr", "© Map contributors"),
                    name=preferred_provider,
                ).add_to(m)

    # Define layers using the configuration
    layers_config = MAP_SETTINGS.get("layers", {})

    # Draw layer
    draw_layer = folium.FeatureGroup(
        name=layers_config.get("draw", {}).get("name", "Draw Layer"),
        show=layers_config.get("draw", {}).get("show", True),
    )

    # Isochrones layer
    isochrones_layer = folium.FeatureGroup(
        name=layers_config.get("isochrones", {}).get("name", "Isochrones"),
        show=layers_config.get("isochrones", {}).get("show", True),
    )

    # Centers layer
    centers_layer = folium.FeatureGroup(
        name=layers_config.get("centers", {}).get("name", "Centers"),
        show=layers_config.get("centers", {}).get("show", True),
    )

    # Locations layer, override the default visibility if include_locations is True
    locations_layer = folium.FeatureGroup(
        name=layers_config.get("locations", {}).get("name", "Locations"),
        show=(
            include_locations
            if include_locations
            else layers_config.get("locations", {}).get("show", False)
        ),
    )

    # Add isochrones using folium.GeoJson for isochrones layer
    with LogContext(layer="isochrones"):
        # Sort features by value in descending order (larger values first)
        # This ensures that larger isochrones are added first and smaller ones appear on top
        sorted_features = sorted(
            isochrones_df["features"],
            key=lambda f: f["properties"].get("value", 0),
            reverse=True,  # Descending order (larger values first)
        )

        for feature in sorted_features:
            center_name = feature["properties"].get("name", "Unknown")
            value = feature["properties"].get("value", 0)
            label = f"{value // 60} minutes" if value else "Unknown"

            folium.GeoJson(
                feature,
                style_function=lambda feature: {
                    "fillColor": feature_colors.get(
                        feature["properties"].get("name", "Unknown"), "gray"
                    ),
                    "color": feature_colors.get(
                        feature["properties"].get("name", "Unknown"), "gray"
                    ),
                    "weight": 2,
                    "fillOpacity": 0.4,
                },
                tooltip=folium.Tooltip(
                    f"Isochrone for {center_name}:&nbsp;<b>{label}</b>"
                ),
            ).add_to(isochrones_layer)

    # Add Center markers and labels to the Centers layer
    with LogContext(layer="centers"):
        for _, row in center_coords.iterrows():
            center_name = row.get(TABLES["centers"]["columns"]["city"], "Unknown")
            center_city = row.get("city", "Unknown")

            latitude = row["latitude"]
            longitude = row["longitude"]

            center_icon = folium.Icon(color="red", icon="tower")
            center_popup = folium.Popup(
                f"<b>{center_name}</b> <br>{center_city}", max_width=300
            )
            center_tooltip = folium.Tooltip(
                f"{center_name}",
                sticky=False,
                permanent=True,
                direction="top",
                offset=(0, -18),
                className="custom-tooltip",
                show=True,
            )

            folium.Marker(
                location=[latitude, longitude],
                popup=center_popup,
                icon=center_icon,
                tooltip=center_tooltip,
            ).add_to(centers_layer)

    # Add Location markers to the Locations layer (if enabled)
    if include_locations and locations_df is not None:
        with LogContext(layer="locations"):
            for _, row in locations_df.iterrows():
                location_id = row.get(TABLES["locations"]["columns"]["name"], "Unknown")
                location_address = row.get("address", "Unknown")
                location_city = row.get("city", "Unknown")
                location_state = row.get("state", "Unknown")
                location_zip = row.get("zip_code", "Unknown")
                location_full_address = f"{location_address}, {location_city}, {location_state} {location_zip}"
                latitude = row.get("latitude")
                longitude = row.get("longitude")

                # Validate coordinates
                if pd.isna(latitude) or pd.isna(longitude):
                    logging.warning(
                        f"Error: Invalid coordinates for location '{location_id}' (latitude: {latitude}, longitude: {longitude}). Skipping..."
                    )
                    continue

                location_icon = folium.Icon(color="blue", icon="camera")
                location_popup = folium.Popup(
                    f"<b>{location_id}</b><br>{location_full_address}",
                    max_width=300,
                )
                location_tooltip = folium.Tooltip(
                    f"<b>{location_id}</b><br>City:&nbsp;{location_city}",
                    sticky=True,
                    direction="top",
                    show=True,
                )

                folium.Marker(
                    location=[latitude, longitude],
                    popup=location_popup,
                    icon=location_icon,
                    tooltip=location_tooltip,
                ).add_to(locations_layer)

    # Add layers to the map
    draw_layer.add_to(m)
    isochrones_layer.add_to(m)
    centers_layer.add_to(m)
    if include_locations:
        locations_layer.add_to(m)

    # Add layer control to toggle layer visibility on the map
    folium.LayerControl(collapsed=True).add_to(m)

    # Define Draw Options
    draw_cnfg = {
        "metric": False,  # Disable metric units
        "feet": False,  # Disable feet
        "nauticalmiles": False,  # Disable nautical miles
    }

    # Add Draw tools
    Draw(
        export=False,
        show_geometry_on_click=False,
        feature_group=draw_layer,
        edit_options={"featureGroup": "editLayer"},
        draw_options={
            "polyline": {
                **draw_cnfg,
                "showLength": True,
            },
            "polygon": {**draw_cnfg, "showArea": True},
            "rectangle": {**draw_cnfg, "showArea": True},
            "circle": {**draw_cnfg, "showRadius": True, "shapeOptions": {}},
        },
    ).add_to(m)

    # Read the contents of map_config.js
    js_file_path = Path(JS, "map_config.js")
    with js_file_path.open("r") as js_file:
        map_config_js = js_file.read()

    # Add a custom script to configure the map
    el = MacroElement().add_to(m)
    el._template = Template(
        f"""
        {{% macro script(this, kwargs) %}}
        const map = {m.get_name()};
        {map_config_js}
        {{% endmacro %}}
        """
    )

    # Add custom CSS for the map
    css_file_path = Path(CSS, "map_styles.css")
    with css_file_path.open("r") as css_file:
        map_css = css_file.read()

    styles = MacroElement().add_to(m)
    styles._template = Template(
        f"""
        {{% macro header(this, kwargs) %}}
        <style>
          {map_css}
        </style>
        {{% endmacro %}}
        """
    )

    return m


@with_log_context(module="maps", operation="minify_html")
def minify_html(file_path):
    """Minify HTML file with structured logging."""
    logging.info(f"Minifying HTML file: {file_path}")

    with Path(file_path).open("r") as file:
        html_content = file.read()

    # Minify <script> tags
    def minify_script(match):
        script_content = match.group(1)
        minified_script = jsmin(script_content, quote_chars="'\"")
        return f"<script>{minified_script}</script>"

    html_content = re.sub(
        r"<script>(.*?)</script>", minify_script, html_content, flags=re.DOTALL
    )

    # Minify <style> tags
    def minify_style(match):
        style_content = match.group(1)
        minified_style = compress(style_content)
        return f"<style>{minified_style}</style>"

    html_content = re.sub(
        r"<style>(.*?)</style>", minify_style, html_content, flags=re.DOTALL
    )

    # Minify the entire HTML, but avoid removing spaces in strings
    minified_html = htmlmin.minify(
        html_content,
        remove_comments=True,
        remove_empty_space=True,
        reduce_boolean_attributes=True,
        remove_optional_attribute_quotes=False,
    )

    with Path(file_path).open("w") as file:
        file.write(minified_html)

    logging.info(f"HTML minification complete for {file_path}")


# Function to load data from local files instead of database
def load_data_local(data_type):
    """Load data from local files instead of database."""
    logging.info(f"Loading {data_type} data from local files")

    if data_type not in TABLES:
        raise ValueError(f"Unknown data type: {data_type}")

    # Get table and file configurations
    table_config = TABLES[data_type]
    table_name = table_config.get("table_name", data_type)

    # Consistent file naming across data types
    file_name = table_config.get("file_name", f"geocoded_{table_name}.csv")
    file_path = Path(DATA, "locations", file_name)

    if not file_path.exists():
        raise DataAccessError(f"{data_type.capitalize()} file not found: {file_path}")

    # Remaining code unchanged...

    if data_type == "centers":
        # Use table_name from config to construct the filename
        file_name = TABLES[data_type].get("file_name", f"geocoded_{table_name}.csv")
        file_path = Path(DATA, "locations", file_name)
    elif data_type == "locations":
        file_name = TABLES[data_type].get("file_name", f"geocoded_{table_name}.csv")
        file_path = Path(DATA, "locations", file_name)
    else:
        raise ValueError(f"Unsupported data type: {data_type}")

    if not file_path.exists():
        raise DataAccessError(f"{data_type.capitalize()} file not found: {file_path}")

    try:
        # Load the CSV file
        logging.info(f"Loading {data_type} from {file_path}")
        df = pd.read_csv(file_path)

        # Validate the required columns
        required_columns = TABLES[data_type].get("columns", {}).values()
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            logging.warning(
                f"Missing required columns in {data_type} data: {missing_columns}"
            )

        return df
    except Exception as e:
        raise DataAccessError(f"Failed to load {data_type} data: {str(e)}")


def load_isochrones_local():
    """Load isochrones data from local GeoJSON files.

    Uses the TABLES configuration to determine appropriate file paths and naming conventions.

    Returns:
        dict: GeoJSON FeatureCollection containing isochrone data

    Raises:
        DataAccessError: If isochrone files cannot be found or loaded
    """
    logging.info("Loading isochrones data from local files")

    isochrones_config = TABLES.get("isochrones", {})
    isochrones_dir = Path(DATA, "isochrones")

    # Get the file name from TABLES config or use default
    combined_file_name = isochrones_config.get("file_name", "isochrones.geojson")
    combined_path = Path(isochrones_dir, combined_file_name)

    # Try to load the combined file first
    if combined_path.exists():
        logging.info(f"Loading combined isochrones from {combined_path}")
        try:
            with open(combined_path, "r") as f:
                return json.load(f)
        except Exception as e:
            raise DataAccessError(f"Failed to load combined isochrones file: {str(e)}")

    # If combined file doesn't exist, load and combine individual isochrone files
    logging.info(
        f"Combined isochrone file not found at {combined_path}, loading individual city files"
    )

    # Determine file pattern from config or use default
    file_pattern = isochrones_config.get(
        "individual_file_pattern", "*_isochrones.geojson"
    )
    individual_files = list(isochrones_dir.glob(file_pattern))

    if not individual_files:
        raise DataAccessError(
            f"No isochrone files matching '{file_pattern}' found in {isochrones_dir}"
        )

    # Start with an empty feature collection
    combined_isochrones = {"type": "FeatureCollection", "features": []}

    # Use the name field from TABLES if available
    name_field = isochrones_config.get("columns", {}).get("name", "name")

    # Load and combine each file
    for file_path in individual_files:
        # Extract isochrone name from filename using configured pattern
        isochrone_name = file_path.stem
        if "_isochrones" in isochrone_name:
            isochrone_name = isochrone_name.replace("_isochrones", "")

        logging.info(f"Loading isochrones for {isochrone_name} from {file_path}")

        try:
            with open(file_path, "r") as f:
                isochrone_data = json.load(f)
        except FileNotFoundError:
            raise DataAccessError(f"Isochrone file not found: {file_path}")
        except json.JSONDecodeError as e:
            raise GeoJSONError(f"Invalid GeoJSON in {file_path}: {str(e)}")
        except Exception as e:
            raise DataAccessError(
                f"Failed to load isochrone file {file_path}: {str(e)}"
            )

        # Add city name to properties if not already present
        for feature in isochrone_data.get("features", []):
            if "properties" in feature and name_field not in feature["properties"]:
                feature["properties"][name_field] = isochrone_name

        # Add features to combined collection
        combined_isochrones["features"].extend(isochrone_data.get("features", []))

    if not combined_isochrones["features"]:
        raise DataAccessError("No valid isochrone features found in any file")

    return combined_isochrones


def validate_map_config():
    """Validate the map configuration."""
    required_settings = ["colors", "layers", "zoom"]
    for setting in required_settings:
        if setting not in MAP_SETTINGS:
            raise ConfigError(f"Missing required map setting: {setting}")

    # Check that each layer has required properties
    for layer_name, layer_config in MAP_SETTINGS.get("layers", {}).items():
        if "name" not in layer_config:
            raise ConfigError(f"Layer {layer_name} missing 'name' property")


# Main funciton with mode support, structured logging, and error handling
@handle_exception(custom_mapping={ValueError: DataAccessError, Exception: GeoJSONError})
@with_log_context(module="maps", operation="main")
def main():
    """Main function to generate maps with mode support."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Generate maps for visualizing isochrones",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate static HTML maps from local files (default mode)
  python -m src.maps --mode use-local

  # Generate maps with satellite imagery
  python -m src.maps --mode use-local --tile-provider Satellite

  # Set up maps for dynamic Flask serving with database
  python -m src.maps --mode use-db

For more information, see the module documentation.
""",
    )
    parser.add_argument(
        "--mode",
        choices=["use-db", "use-local"],
        default="use-local",
        help="Processing mode: 'use-db' to serve maps via Flask/database, 'use-local' to generate static HTML files from local data (default: use-local)",
    )
    parser.add_argument(
        "--tile-provider",
        help="Map tile provider to use (e.g., 'OpenStreetMap', 'Satellite', 'CartoDB'). See MAP_SETTINGS for available providers.",
    )
    args = parser.parse_args()

    logging.info(f"Starting map generation process in {args.mode} mode")

    if args.mode == "use-local":
        # Generate static HTML map files from local data
        maps = generate_maps(use_local=True, tile_provider=args.tile_provider)
        logging.info(f"Maps generated successfully in {args.mode} mode: {maps}")
        return maps
    elif args.mode == "use-db":
        # In use-db mode, we just ensure the Flask routes are set up
        # No need to generate maps here, as they'll be created dynamically
        logging.info(f"Map service configured for Flask in {args.mode} mode")
        return {
            "mode": "use-db",
            "status": "configured",
            "tile_provider": args.tile_provider,
        }


if __name__ == "__main__":
    try:
        result = main()
        logging.info(f"Map processing complete: {result}")
    except Exception as e:
        logging.error(f"Failed to process maps: {e}", exc_info=True)
        raise
