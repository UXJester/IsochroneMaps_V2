"""
Isochrone Generation Module
===========================

This module generates travel time isochrones (areas reachable within specific time limits)
around geographic centers using the OpenRouteService API. It supports both database-backed
and file-based workflows, allowing for flexible deployment scenarios.

Key Features:
------------
* Two operating modes:
  - Database mode ('use-db'): Reads centers from and writes isochrones to Supabase
  - Local mode ('use-local'): Reads from local CSV files and writes to GeoJSON files
* Multi-range isochrone generation (default: 30 and 60 minute travel times)
* Parallel processing with configurable worker threads
* Comprehensive error handling and structured logging
* Optional dry-run capability for testing without writing data

Main Functions:
-------------
* load_center_data: Load center coordinates from Supabase or local CSV files
* generate_isochrone: Generate isochrones for a single center using OpenRouteService
* upsert_isochrones: Save isochrone data to the Supabase database
* save_geojson_file: Save GeoJSON isochrone data to local files
* check_existing_isochrones: Check for existing isochrones in the database
* main: Command-line entry point with argument parsing

Command-line Usage:
-----------------
# Generate isochrones from database centers and store in database
$ python -m src.isochrone --mode use-db

# Generate isochrones from CSV centers and save as GeoJSON files
$ python -m src.isochrone --mode use-local

# Perform a dry run without writing to database or files
$ python -m src.isochrone --dry-run

Dependencies:
------------
* OpenRouteService API client (requires API key)
* Supabase client for database operations (in 'use-db' mode)
* pandas for data processing
* Local files: centers CSV file in the LOCATIONS directory (for 'use-local' mode)

Example:
-------
>>> from src.isochrone import generate_isochrone
>>> from src.utils.client_utils import get_ors_client
>>> client = get_ors_client()
>>> center_name = "Test Center"
>>> result = generate_isochrone(client, -122.4194, 37.7749, center_name)
>>> # result contains GeoJSON data for the isochrones
"""

# Standard Library Imports
import os
import sys
import json
import logging
import re
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import sleep

# Add the project root to the Python path before other project imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Third-party Imports
from openrouteservice.isochrones import isochrones
import pandas as pd

# Local Imports
from src.utils.logging_utils import (
    setup_structured_logging,
    with_log_context,
    LogContext,
)
from src.utils.error_utils import (
    handle_exception,
    ExceptionContext,
    DataAccessError,
    APIConnectionError,
    DataProcessingError,
    DataValidationError,
    GeoJSONError,
)
from src.utils.data_utils import load_data
from src.utils.client_utils import get_supabase_client, get_ors_client
from src.config import ISOCHRONES, TABLES, LOCATIONS

# Configure structured logging
setup_structured_logging(log_file="isochrone.log")


@handle_exception(
    custom_mapping={ValueError: DataValidationError, Exception: DataProcessingError}
)
@with_log_context(module="isochrone", operation="load_centers")
def load_center_data(supabase=None, mode="use-db"):
    """
    Load center data from Supabase or local CSV files and extract coordinates.

    Args:
        supabase: Supabase client instance (required for use-db mode)
        mode: Data source mode - 'use-db' for Supabase, 'use-local' for CSV files

    Returns:
        tuple: (centers_df, coords_list) containing the DataFrame and coordinates

    Raises:
        DataValidationError: If centers data is empty or missing coordinates
        DataAccessError: If database/file access fails
    """
    centers_table = TABLES["centers"]
    columns = centers_table["columns"]

    # Load data from the appropriate source based on mode
    if mode == "use-local":
        # Determine path to geocoded centers file
        geocoded_file = Path(LOCATIONS) / f"geocoded_{centers_table['table_name']}.csv"
        original_file = Path(LOCATIONS) / f"{centers_table['table_name']}.csv"

        # Use geocoded file if it exists, otherwise use original
        file_path = geocoded_file if geocoded_file.exists() else original_file

        logging.info(f"Loading center data from file: {file_path}")

        try:
            # Load CSV file into DataFrame
            centers_df = pd.read_csv(file_path, dtype={"id": "int"})
        except FileNotFoundError:
            logging.error(f"Center data file not found: {file_path}")
            raise DataAccessError(f"Center data file not found: {file_path}")
    else:
        # Load from Supabase
        if not supabase:
            logging.error("Supabase client is required for use-db mode")
            raise DataAccessError("Supabase client is required for use-db mode")

        logging.info(f"Loading center data from table: {centers_table['table_name']}")
        centers_df = load_data(
            supabase, centers_table["table_name"], dtype={"id": "int"}
        )

    # Validate the loaded data
    if centers_df.empty:
        logging.error("Center data is empty")
        raise DataValidationError("Center data is empty")

    # Extract coordinates for each center
    coords_list = []
    for i, center in centers_df.iterrows():
        center_name = center[columns["city"]]

        with LogContext(center_name=center_name, center_id=i):
            latitude = center[columns["latitude"]]
            longitude = center[columns["longitude"]]

            if pd.isna(latitude) or pd.isna(longitude):
                logging.error(f"Center '{center_name}' has missing coordinates")
                raise DataValidationError(
                    f"Center '{center_name}' has missing coordinates"
                )

            coords_list.append(
                [longitude, latitude]  # OpenRouteService expects [longitude, latitude]
            )
            logging.debug(f"Added center coordinates: [{longitude}, {latitude}]")

    logging.info(f"Successfully loaded {len(coords_list)} centers with coordinates")
    return centers_df, coords_list


@handle_exception(custom_mapping={Exception: APIConnectionError})
@with_log_context(module="isochrone", operation="generate_isochrone")
def generate_isochrone(client, longitude, latitude, center_name):
    """
    Generate isochrones for a single center using OpenRouteService.

    Args:
        client: The OpenRouteService client instance
        longitude: The longitude coordinate of the center
        latitude: The latitude coordinate of the center
        center_name: The name of the center

    Returns:
        tuple: (center_name, isochrone_result) where isochrone_result is GeoJSON or None

    Raises:
        APIConnectionError: If the ORS service cannot be reached or returns an error
    """
    with LogContext(center=center_name, coords=[longitude, latitude]):
        logging.info(f"Generating isochrones for {center_name}")

        try:
            with ExceptionContext("OpenRouteService API call", APIConnectionError):
                isochrone_result = isochrones(
                    client,
                    locations=[[longitude, latitude]],
                    profile="driving-car",
                    range=[3600, 1800],  # 60 and 30 minutes
                    range_type="time",
                    smoothing=25,
                )

            logging.info(f"Generated isochrones for {center_name} successfully")
            return center_name, isochrone_result

        except Exception as e:
            logging.error(f"Error generating isochrones for {center_name}: {e}")
            raise

        finally:
            # Optional: Sleep to avoid hitting API rate limits
            sleep(1.5)


@handle_exception(
    custom_mapping={ValueError: DataValidationError, Exception: DataProcessingError}
)
@with_log_context(module="isochrone", operation="upsert_isochrones")
def upsert_isochrones(
    supabase_client, center_name, isochrone_result, dry_run=False, centers_df=None
):
    """
    Save isochrone data to the Supabase database using upsert operations.

    Args:
        supabase_client: The Supabase client instance
        center_name: The name of the center associated with the isochrones
        isochrone_result: GeoJSON result from OpenRouteService
        dry_run: Whether to simulate the operation without writing to the database
        centers_df: DataFrame containing center information

    Raises:
        DataValidationError: If input data is invalid
        DataProcessingError: If the upsert operation fails
        GeoJSONError: If there are issues with GeoJSON geometry
    """
    with LogContext(center_name=center_name, dry_run=dry_run):
        logging.info(f"Processing isochrones for {center_name}")

        # Extract metadata from the isochrone result
        full_metadata = isochrone_result.get("metadata", {})
        isochrones_table = TABLES["isochrones"]
        isochrones_columns = isochrones_table["columns"]
        centers_table = TABLES["centers"]
        centers_columns = centers_table["columns"]

        # Get state and zip_code information from centers_df
        state = None
        zip_code = None
        if centers_df is not None:
            center_row = centers_df[centers_df[centers_columns["city"]] == center_name]
            if not center_row.empty:
                if centers_columns["state"] in center_row.columns:
                    state = center_row[centers_columns["state"]].iloc[0]
                    logging.debug(f"Found state '{state}' for center '{center_name}'")

                if centers_columns["zip_code"] in center_row.columns:
                    zip_code = center_row[centers_columns["zip_code"]].iloc[0]
                    logging.debug(
                        f"Found zip_code '{zip_code}' for center '{center_name}'"
                    )
            else:
                logging.warning(f"Center information not found for '{center_name}'")

        # If state or zip_code is still None, attempt to get it from the database
        if state is None or zip_code is None:
            with ExceptionContext("Retrieving center information", DataAccessError):
                center_data = (
                    supabase_client.table(centers_table["table_name"])
                    .select(
                        f"{centers_columns['state']}, {centers_columns['zip_code']}"
                    )
                    .eq(centers_columns["city"], center_name)
                    .execute()
                )
                if center_data.data and len(center_data.data) > 0:
                    if state is None:
                        state = center_data.data[0].get(centers_columns["state"])
                        logging.debug(
                            f"Retrieved state '{state}' for center '{center_name}' from database"
                        )

                    if zip_code is None:
                        zip_code = center_data.data[0].get(centers_columns["zip_code"])
                        logging.debug(
                            f"Retrieved zip_code '{zip_code}' for center '{center_name}' from database"
                        )
                else:
                    logging.error(
                        f"Could not find center information for '{center_name}'"
                    )
                    raise DataValidationError(
                        f"Center information missing for '{center_name}'"
                    )

        if state is None:
            logging.error(f"State information missing for center '{center_name}'")
            raise DataValidationError(
                f"State information missing for center '{center_name}'"
            )

        if zip_code is None:
            logging.error(f"Zip code information missing for center '{center_name}'")
            raise DataValidationError(
                f"Zip code information missing for center '{center_name}'"
            )

        for i, feature in enumerate(isochrone_result["features"]):
            with LogContext(feature_idx=i):
                group_index = feature["properties"]["group_index"]
                value = feature["properties"]["value"]
                center = feature["properties"]["center"]
                geometry = feature["geometry"]

                # Convert center and geometry to WKT format for PostGIS
                center_wkt = f"POINT({center[0]} {center[1]})"

                # Use GeoJSONError for geometry-specific validation errors
                try:
                    if geometry["type"] != "Polygon":
                        logging.error(
                            f"Expected Polygon geometry, got {geometry['type']}"
                        )
                        raise GeoJSONError(
                            f"Expected Polygon geometry, got {geometry['type']}"
                        )

                    coordinates = geometry["coordinates"][0]
                    if not coordinates or len(coordinates) < 4:
                        logging.error("Invalid polygon: insufficient coordinates")
                        raise GeoJSONError("Invalid polygon: insufficient coordinates")

                    polygon_wkt = (
                        "POLYGON(("
                        + ", ".join(f"{x[0]} {x[1]}" for x in coordinates)
                        + "))"
                    )
                except (KeyError, IndexError) as e:
                    logging.error(f"Invalid GeoJSON geometry structure: {e}")
                    raise GeoJSONError(f"Invalid GeoJSON geometry structure: {e}")
                except Exception as e:
                    logging.error(f"Unexpected geometry error: {e}")
                    raise GeoJSONError(f"Unexpected geometry error: {e}")

                # Combine feature properties with the full metadata
                metadata = {**full_metadata}

                # Check if the row already exists and retrieve its ID
                with ExceptionContext("Querying existing isochrones", DataAccessError):
                    existing_row = (
                        supabase_client.table(isochrones_table["table_name"])
                        .select(isochrones_columns["id"])
                        .eq(isochrones_columns["name"], center_name)
                        .eq(isochrones_columns["group_index"], group_index)
                        .eq(isochrones_columns["value"], value)
                        .execute()
                    )

                # Prepare upsert data
                upsert_data = {
                    isochrones_columns["name"]: center_name,
                    isochrones_columns["state"]: state,
                    isochrones_columns["zip_code"]: zip_code,
                    isochrones_columns["group_index"]: group_index,
                    isochrones_columns["value"]: value,
                    isochrones_columns["center"]: center_wkt,
                    isochrones_columns["geometry"]: polygon_wkt,
                    isochrones_columns["metadata"]: metadata,
                }

                if dry_run:
                    # Log the data instead of upserting
                    logging.info(
                        f"Dry run: would upsert isochrone for {center_name}, state={state}, zip_code={zip_code}, value={value}"
                    )
                else:
                    # Determine if we should insert or update based on existing data
                    if existing_row.data:
                        row_id = existing_row.data[0][isochrones_columns["id"]]
                        logging.debug(f"Found existing isochrone with ID: {row_id}")

                        # Update existing record by ID
                        with ExceptionContext(
                            "Updating isochrone data", DataProcessingError
                        ):
                            response = (
                                supabase_client.table(isochrones_table["table_name"])
                                .update(upsert_data)
                                .eq(isochrones_columns["id"], row_id)
                                .execute()
                            )
                    else:
                        # Insert new record
                        logging.debug(
                            "No existing isochrone found, will insert new record"
                        )
                        with ExceptionContext(
                            "Inserting isochrone data", DataProcessingError
                        ):
                            response = (
                                supabase_client.table(isochrones_table["table_name"])
                                .insert(upsert_data)
                                .execute()
                            )

                    # Check if the response contains an error
                    if hasattr(response, "error") and response.error:
                        logging.error(f"Failed to upsert isochrone: {response.error}")
                        raise DataProcessingError(
                            f"Failed to upsert isochrone: {response.error}"
                        )
                    elif hasattr(response, "data") and response.data:
                        logging.info("Upserted isochrone successfully")
                    else:
                        logging.warning(f"Unexpected response format: {response}")


@handle_exception(custom_mapping={Exception: DataAccessError})
@with_log_context(module="isochrone", operation="check_existing_isochrones")
def check_existing_isochrones(supabase_client):
    """
    Check if any isochrone records already exist in the database.

    Args:
        supabase_client: The Supabase client instance

    Returns:
        bool: True if records exist, False otherwise

    Raises:
        DataAccessError: If database access fails
    """
    isochrones_table = TABLES["isochrones"]

    try:
        with ExceptionContext("Checking for existing isochrones", DataAccessError):
            # Query just a count to avoid retrieving all data
            result = (
                supabase_client.table(isochrones_table["table_name"])
                .select("*", count="exact")
                .limit(1)
                .execute()
            )

            # Check if any records were found using the count property
            record_count = (
                result.count if hasattr(result, "count") else len(result.data)
            )
            exists = record_count > 0

            if exists:
                logging.info(
                    f"Found {record_count} existing isochrone records in database"
                )
            else:
                logging.info("No existing isochrone records found in database")

            return exists

    except Exception as e:
        logging.error(f"Error checking for existing isochrones: {e}")
        raise DataAccessError(f"Failed to check for existing isochrones: {e}")


@handle_exception(
    custom_mapping={Exception: DataProcessingError, json.JSONDecodeError: GeoJSONError}
)
@with_log_context(module="isochrone", operation="save_geojson")
def save_geojson_file(file_path, data):
    """
    Save GeoJSON data to a file.

    Args:
        file_path: Path to save the file
        data: GeoJSON data to save

    Raises:
        DataProcessingError: If file saving fails
        GeoJSONError: If JSON serialization fails
    """
    try:
        with file_path.open("w") as f:
            json.dump(data, f)
        logging.info(f"Saved GeoJSON to {file_path}")
    except json.JSONDecodeError as e:
        logging.error(f"GeoJSON serialization error: {e}")
        raise GeoJSONError(f"GeoJSON serialization error: {e}")
    except Exception as e:
        logging.error(f"Error saving GeoJSON file: {e}")
        raise DataProcessingError(f"Error saving GeoJSON to {file_path}: {e}")


@handle_exception
@with_log_context(module="isochrone", operation="main")
def main():
    """Main function to generate and save isochrones."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Generate travel time isochrones around centers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate isochrones and store in database (default mode)
  python -m src.isochrone --mode use-db

  # Generate isochrones and save as local GeoJSON files
  python -m src.isochrone --mode use-local

  # Perform a dry run without modifying the database
  python -m src.isochrone --dry-run

For more information, see the module documentation.
""",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate operations without writing to the database or creating files",
    )
    parser.add_argument(
        "--mode",
        choices=["use-db", "use-local"],
        default="use-local",
        help="Processing mode: 'use-db' to store isochrones in the database, 'use-local' to use geocoded CSV files from LOCATIONS directory and save as GeoJSON files (default: use-db)",
    )
    args = parser.parse_args()

    logging.info(
        f"Starting isochrone generation process (mode={args.mode}, dry_run={args.dry_run})"
    )

    # Initialize OpenRouteService client
    with LogContext(action="initialize_clients"):
        ors_client = get_ors_client()
        if not ors_client:
            raise APIConnectionError("Failed to initialize OpenRouteService client")

        # Only initialize Supabase client when needed (for database operations)
        supabase = None
        if args.mode == "use-db":
            supabase = get_supabase_client()
            if not supabase:
                raise DataAccessError("Failed to initialize Supabase client")

    # Check if any files exist in the ISOCHRONES folder - only in use-local mode
    isochrones_path = Path(ISOCHRONES)
    isochrones_path.mkdir(parents=True, exist_ok=True)

    if args.mode == "use-local":
        with LogContext(action="check_existing_files"):
            # Use glob to list all files in the folder, ignoring hidden files
            existing_files = [
                f
                for f in isochrones_path.glob("*")
                if f.is_file() and not f.name.startswith(".")
            ]

            if existing_files:
                logging.info(f"Found {len(existing_files)} existing isochrone files")
                confirm = (
                    input(
                        "Do you want to generate new isochrones and potentially overwrite existing files? (y/n): "
                    )
                    .strip()
                    .lower()
                )

                if confirm != "y":
                    logging.info("Aborting isochrone generation")
                    return
    elif args.mode == "use-db":
        with LogContext(action="check_existing_records"):
            # Check if there are existing isochrone records in the database
            if check_existing_isochrones(supabase):
                confirm = (
                    input(
                        "Do you want to generate new isochrones and potentially update existing database records? (y/n): "
                    )
                    .strip()
                    .lower()
                )

                if confirm != "y":
                    logging.info("Aborting isochrone generation")
                    return

    # Load center data based on selected mode
    with LogContext(action=f"load_center_data_from_{args.mode}"):
        if args.mode == "use-local":
            centers_df, coords_list = load_center_data(None, args.mode)
        else:
            # Initialize Supabase client for database operations if not already initialized
            if supabase is None:
                with LogContext(action="initialize_supabase_for_center_data"):
                    supabase = get_supabase_client()
                    if not supabase:
                        raise DataAccessError(
                            "Failed to initialize Supabase client for center data"
                        )
            centers_df, coords_list = load_center_data(supabase, args.mode)

    # Generate isochrones in parallel
    isochrones_data = {}
    logging.info(f"Generating isochrones for {len(coords_list)} centers")

    with LogContext(action="generate_isochrones"):
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_to_center = {
                executor.submit(
                    generate_isochrone,
                    ors_client,
                    longitude,
                    latitude,
                    centers_df.iloc[index][TABLES["centers"]["columns"]["city"]],
                ): index
                for index, (longitude, latitude) in enumerate(coords_list)
            }

            for future in as_completed(future_to_center):
                try:
                    center_name, isochrone_result = future.result()
                    if isochrone_result:
                        isochrones_data[center_name] = isochrone_result
                except Exception as e:
                    logging.error(f"Failed to get future result: {e}")

    # Process the isochrone data based on the selected mode
    if args.mode == "use-local":
        # Save individual isochrones to GeoJSON files in use-local mode
        with LogContext(action="save_individual_files"):
            for center_name, isochrone_result in isochrones_data.items():
                file_name = re.sub(r"[^a-zA-Z0-9]", "", center_name)
                output_file = Path(isochrones_path, f"{file_name}_isochrones.geojson")
                save_geojson_file(output_file, isochrone_result)

        # Save all isochrones data to a single GeoJSON file
        with LogContext(action="save_combined_file"):
            output_file = Path(isochrones_path, "isochrones.geojson")

            # Combine all isochrones into a single GeoJSON FeatureCollection
            combined_isochrones = {"type": "FeatureCollection", "features": []}

            for center_name, result in isochrones_data.items():
                for feature in result["features"]:
                    # Add name to properties for identification
                    feature["properties"]["name"] = center_name
                    combined_isochrones["features"].append(feature)

            save_geojson_file(output_file, combined_isochrones)

        logging.info("GeoJSON files saved successfully to local files")

    else:  # use-db mode
        # Save individual isochrones to Supabase
        with LogContext(action="save_to_database", dry_run=args.dry_run):
            for center_name, isochrone_result in isochrones_data.items():
                upsert_isochrones(supabase, center_name, isochrone_result, args.dry_run)

        logging.info("Isochrones saved successfully to database")

    logging.info(
        f"Isochrone generation process completed successfully (mode={args.mode})"
    )


if __name__ == "__main__":
    main()
