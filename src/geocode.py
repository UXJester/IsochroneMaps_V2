"""
Geocoding Module
===============

A comprehensive geocoding utility that converts addresses to geographic coordinates (latitude, longitude)
using the Nominatim geocoding service. Supports both individual address geocoding and batch processing
from multiple data sources.

Key Features:
-------------
* Multi-stage fallback geocoding strategy:
  1. First attempts exact address geocoding
  2. If unsuccessful, tries location name (if provided)
  3. Fallback to city/state/zip if specific address fails
* Multiple data source support:
  - Database tables (via Supabase)
  - Local CSV files
* Efficient processing:
  - Only geocodes records with missing or erroneous coordinates
  - Tracks which records need updating
* Comprehensive error handling and structured logging

Operating Modes:
---------------
* Database mode ('use-db'): Reads from and writes to database tables
* CSV mode ('use-local'): Processes local CSV files, creating geocoded versions

Functions:
---------
* initialize_geolocator: Initialize a secure geolocator with SSL context
* geocode: Geocode a single address with multi-stage fallback
* geocode_dataset: Process any DataFrame regardless of source
* process_csv_source: Process a CSV file source
* process_db_source: Process a table from the database
* main: Command-line entry point with mode selection

Dependencies:
------------
* Standard Library:
  - os, sys: Path handling and file operations
  - ssl: Secure connection for geocoding service
  - logging: Enhanced logging capabilities
  - argparse: Command-line argument parsing

* External Libraries:
  - pandas: Data manipulation and CSV handling
  - geopy: Geocoding functionality (Nominatim service)
  - certifi: SSL certificate validation

* Project Components:
  - src.utils: Logging, error handling, and client utilities
  - src.config: Table configurations and path definitions

Usage Examples:
--------------
1. As a library (importing functions):
   >>> from src.geocode import geocode
   >>> # Basic address geocoding
   >>> lat, lon, error = geocode("1600 Pennsylvania Ave", "Washington", "DC", "20500")
   >>> print(f"Coordinates: ({lat}, {lon})")
   >>> # Using location name when address is unavailable
   >>> lat, lon, error = geocode("", "Herod", "IL", "62946", location_name="Shawnee National Forest")
   >>> print(f"Coordinates: ({lat}, {lon})")

2. As a command-line tool:
   # Process database tables
   $ python -m src.geocode --mode use-db

   # Process local CSV files
   $ python -m src.geocode --mode use-local
"""

# Standard Library Imports
import os
import sys
import ssl
import logging
import argparse
import pandas as pd

# Add the project root to the Python path before other project imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Third-party Imports
import certifi
from geopy.geocoders import Nominatim

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
)
from src.utils.data_utils import load_data
from src.utils.client_utils import get_supabase_client
from src.config import TABLES, LOCATIONS

# Configure structured logging
setup_structured_logging(log_file="geocode.log")


@handle_exception(
    custom_mapping={
        ssl.SSLError: APIConnectionError,
        TimeoutError: APIConnectionError,
        Exception: APIConnectionError,
    }
)
@with_log_context(module="geocode", operation="initialize_geolocator")
def initialize_geolocator():
    """Initialize and return a geolocator with secure SSL context."""
    logging.info("Initializing geolocator")

    # Create a secure SSL context
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    # Initialize geolocator with increased timeout
    geolocator = Nominatim(user_agent="geo_mapper", ssl_context=ssl_context, timeout=10)

    logging.info("Geolocator initialized successfully")
    return geolocator


@handle_exception(custom_mapping={Exception: APIConnectionError})
@with_log_context(module="geocode", operation="geocode_address")
def geocode(address, city, state, zip_code, geolocator=None, location_name=None):
    """
    Geocode an address and return latitude, longitude, and error.
    If address geocoding fails but location_name is provided, will attempt to geocode using the location name.

    Args:
        address: Street address
        city: City name
        state: State name
        zip_code: ZIP code
        geolocator: Optional geolocator instance (creates one if None)
        location_name: Optional name of a location (like a park, landmark, etc.)

    Returns:
        tuple: (latitude, longitude, error_message)

    Raises:
        APIConnectionError: If geocoding service cannot be reached
    """
    # Create geolocator if not provided
    if not geolocator:
        geolocator = initialize_geolocator()

    # Ensure address is a string to prevent NaN/float errors
    if address is None or (isinstance(address, float) and pd.isna(address)):
        address = ""

    # Try with address first
    if address and str(address).strip() != "":
        full_address = ", ".join(
            filter(None, [str(address), str(city), str(state), str(zip_code)])
        )

        with LogContext(address=full_address):
            logging.info(f"Geocoding address: {full_address}")

            try:
                # Use ExceptionContext for geocoding operation
                with ExceptionContext("Geocoding address", APIConnectionError):
                    location = geolocator.geocode(full_address)

                if location:
                    # Log the raw geocoder response data structure
                    logging.info(f"Geocoder raw response: {location.raw}")

                    logging.info(
                        f"Geocoded successfully: {full_address} -> ({location.latitude}, {location.longitude})"
                    )
                    return location.latitude, location.longitude, ""
                else:
                    logging.warning(f"Location not found for address: {full_address}")
                    # Will fall through to location name geocoding if provided
            except Exception as e:
                logging.warning(f"error geocoding '{full_address}': {e}")
                # Will fall through to location name geocoding if provided

    # Try with location name if provided (either as primary method or fallback)
    if location_name:
        # Log raw address components
        logging.info(
            f"Raw address components: address='{address}', city='{city}', state='{state}', zip_code='{zip_code}'"
        )

        # Use only the location name
        location_query = location_name

        with LogContext(location_name=location_name):
            logging.info(f"Geocoding by location name: {location_query}")

            try:
                # Use ExceptionContext for geocoding operation
                with ExceptionContext("Geocoding location name", APIConnectionError):
                    location = geolocator.geocode(location_query)

                if location:
                    # Log the raw geocoder response data structure
                    logging.info(f"Geocoder raw response: {location.raw}")

                    logging.info(
                        f"Geocoded successfully by location name: {location_query} -> ({location.latitude}, {location.longitude})"
                    )
                    return location.latitude, location.longitude, ""
                else:
                    logging.warning(f"Location not found by name: {location_query}")
                    # Will fall through to city, state, zip_code geocoding
            except Exception as e:
                logging.error(
                    f"error geocoding by location name '{location_query}': {e}"
                )
                # Will fall through to city, state, zip_code geocoding

    # Try with city, state, zip_code as a fallback when neither address nor location_name worked
    if city or state or zip_code:
        city_state_zip = ", ".join(filter(None, [str(city), str(state), str(zip_code)]))

        with LogContext(city_state_zip=city_state_zip):
            logging.info(
                f"Fallback geocoding with city, state, zip_code: {city_state_zip}"
            )

            try:
                # Use ExceptionContext for geocoding operation
                with ExceptionContext("Geocoding city,state,zip", APIConnectionError):
                    location = geolocator.geocode(city_state_zip)

                if location:
                    # Log the raw geocoder response data structure
                    logging.info(f"Geocoder raw response: {location.raw}")

                    logging.info(
                        f"Geocoded successfully with city,state,zip: {city_state_zip} -> ({location.latitude}, {location.longitude})"
                    )
                    # Only set error flag for manual review if there was a valid address that wasn't found
                    error_message = ""
                    if address and str(address).strip() != "":
                        error_message = "Geocoded to city center - needs manual review"

                    return (
                        location.latitude,
                        location.longitude,
                        error_message,
                    )
                else:
                    logging.warning(
                        f"Location not found for city,state,zip: {city_state_zip}"
                    )
                    return None, None, "Location not found"
            except Exception as e:
                logging.error(
                    f"error geocoding by city,state,zip '{city_state_zip}': {e}"
                )
                return None, None, str(e)

    # If we get here, all geocoding attempts failed
    return None, None, "Location not found"


@handle_exception(
    custom_mapping={
        DataAccessError: DataAccessError,
        APIConnectionError: APIConnectionError,
        Exception: DataProcessingError,
    }
)
@with_log_context(module="geocode", operation="geocode_dataset")
def geocode_dataset(data, columns_config, geolocator=None):
    """
    Generic function to geocode any dataset (DataFrame) regardless of source.

    Args:
        data: DataFrame containing records to geocode
        columns_config: Dictionary mapping column roles to column names
        geolocator: Optional geolocator instance (creates one if None)

    Returns:
        DataFrame with geocoded records, success_count, error_count
    """
    if geolocator is None:
        geolocator = initialize_geolocator()

    # Ensure required columns exist
    for col in ["latitude", "longitude", "error"]:
        col_name = columns_config.get(col, col)
        if col_name not in data.columns:
            data[col_name] = None

    # Add a flag to track which rows need updates
    data["_needs_update"] = False

    # Filter rows that need geocoding
    rows_to_process = data[
        data[columns_config["latitude"]].isna()
        | data[columns_config["longitude"]].isna()
        | (data["error"].notna() & (data["error"] != ""))
    ]

    if rows_to_process.empty:
        logging.info("All records are already geocoded")
        return data, 0, 0

    logging.info(f"Found {len(rows_to_process)} records that need geocoding")

    success_count = 0
    error_count = 0

    # Process each row
    for index, row in rows_to_process.iterrows():
        # Get location name if available
        location_name = row.get("name", None) if "name" in columns_config else None

        # Extract address components
        address = row.get(columns_config.get("address", ""), "")
        city = row.get(columns_config["city"], "")
        state = row.get(columns_config["state"], "")
        zip_code = row.get(columns_config["zip_code"], "")

        # Geocode
        with LogContext(record_id=index):
            lat, lon, error = geocode(
                address,
                city,
                state,
                zip_code,
                geolocator=geolocator,
                location_name=location_name,
            )

            # Update the row
            data.at[index, columns_config["latitude"]] = lat
            data.at[index, columns_config["longitude"]] = lon
            data.at[index, "error"] = error
            data.at[index, "_needs_update"] = True

            # Count success/failure
            if lat is not None and lon is not None:
                success_count += 1
                # Only clear error if there isn't one from geocode function
                if not error:
                    data.at[index, "error"] = None
                logging.info(f"Successfully geocoded record {index}")
            else:
                error_count += 1
                logging.warning(f"Failed to geocode record {index}: {error}")

    logging.info(f"Geocoding complete. {success_count} succeeded, {error_count} failed")
    return data, success_count, error_count


@handle_exception(custom_mapping={Exception: DataAccessError})
@with_log_context(module="geocode", operation="load_csv_data")
def load_csv_data(file_path, dtype=None):
    """
    Load data from a CSV file.

    Args:
        file_path: Path to CSV file
        dtype: Data types for columns (optional)

    Returns:
        pandas.DataFrame with loaded data

    Raises:
        DataAccessError: If file cannot be loaded
    """
    with LogContext(file=file_path):
        logging.info(f"Loading CSV data from {file_path}")

        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path, dtype=dtype)
                logging.info(f"Successfully loaded {len(df)} rows from {file_path}")
                return df
            except Exception as e:
                logging.error(f"Failed to load CSV: {e}")
                raise DataAccessError(f"Failed to load CSV file {file_path}: {e}")
        else:
            logging.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"{file_path} not found.")


@handle_exception(custom_mapping={Exception: DataProcessingError})
@with_log_context(module="geocode", operation="process_csv_source")
def process_csv_source(input_file, output_file, columns_config):
    """Process a single CSV data source."""
    with LogContext(input=input_file, output=output_file):
        # Load data
        data = load_csv_data(input_file, dtype={"zip_code": str})
        logging.info(f"Loaded {len(data)} rows from {input_file}")

        # Process geocoding
        geolocator = initialize_geolocator()
        processed_data, success_count, error_count = geocode_dataset(
            data, columns_config, geolocator
        )

        # Save results if any changes were made
        if success_count > 0 or error_count > 0:
            # Remove the temporary tracking column
            if "_needs_update" in processed_data.columns:
                processed_data = processed_data.drop(columns=["_needs_update"])

            processed_data.to_csv(output_file, index=False)
            logging.info(f"Saved {len(processed_data)} rows to {output_file}")
        else:
            logging.info(f"No changes needed for {input_file}")


@handle_exception(
    custom_mapping={
        DataAccessError: DataAccessError,
        APIConnectionError: APIConnectionError,
        Exception: DataProcessingError,
    }
)
@with_log_context(module="geocode", operation="process_csv_mode")
def process_csv_mode():
    """Process geocoding in CSV mode with structured error handling."""
    logging.info("Starting CSV-based geocoding process...")

    # Process each table configuration that needs geocoding
    for table_name, table_config in TABLES.items():
        # Only process tables that need geocoding
        if table_config.get("needs_geocoding", False):
            try:
                with ExceptionContext(
                    f"Processing {table_name} CSV file", DataAccessError
                ):
                    # Check if geocoded file exists
                    original_file = f"{LOCATIONS}/{table_config['table_name']}.csv"
                    geocoded_file = (
                        f"{LOCATIONS}/geocoded_{table_config['table_name']}.csv"
                    )

                    # Use geocoded file as input if it exists
                    input_file = (
                        geocoded_file
                        if os.path.exists(geocoded_file)
                        else original_file
                    )

                    process_csv_source(
                        input_file,
                        geocoded_file,
                        table_config["columns"],
                    )
            except Exception as e:
                logging.error(f"Failed processing {table_name} CSV: {e}")

    logging.info("CSV-based geocoding process completed")


@handle_exception(
    custom_mapping={
        KeyError: DataAccessError,
        ValueError: DataAccessError,
        Exception: DataProcessingError,
    }
)
@with_log_context(module="geocode", operation="process_db_source")
def process_db_source(table_config, supabase_client):
    """
    Process a table to geocode missing or erroneous latitude/longitude.

    Args:
        table_config: Configuration dictionary for the table
        supabase_client: Initialized Supabase client

    Raises:
        DataAccessError: If database access fails
        DataProcessingError: For other processing errors
    """
    table_name = table_config["table_name"]
    columns = table_config["columns"]

    with LogContext(table=table_name):
        logging.info(f"Processing table: {table_name}")

        # Load data from the table
        data = load_data(supabase_client, table_name)
        logging.info(f"Loaded {len(data)} rows from table: {table_name}")

        # Process geocoding
        geolocator = initialize_geolocator()
        processed_data, success_count, error_count = geocode_dataset(
            data, columns, geolocator
        )

        # Update records in database
        if success_count > 0 or error_count > 0:
            rows_updated = 0
            for _, row in processed_data[processed_data["_needs_update"]].iterrows():
                row_id = row[columns["id"]]

                try:
                    supabase_client.table(table_name).update(
                        {
                            columns["latitude"]: row[columns["latitude"]],
                            columns["longitude"]: row[columns["longitude"]],
                            "error": row["error"],
                        }
                    ).eq(columns["id"], row_id).execute()

                    rows_updated += 1
                    logging.info(f"Updated row ID {row_id} in table: {table_name}")

                except Exception as e:
                    logging.error(f"Failed to update row ID {row_id}: {e}")

            logging.info(f"Updated {rows_updated} rows in database table {table_name}")
        else:
            logging.info(f"No updates needed for table {table_name}")


@handle_exception(
    custom_mapping={
        DataAccessError: DataAccessError,
        APIConnectionError: APIConnectionError,
        Exception: DataProcessingError,
    }
)
@with_log_context(module="geocode", operation="process_db_mode")
def process_db_mode():
    """Process geocoding in DB mode with structured error handling."""
    logging.info("Starting database-based geocoding process...")

    # Initialize Supabase client
    with LogContext(action="initialize_client"):
        supabase_client = get_supabase_client()
        if not supabase_client:
            raise DataAccessError("Failed to initialize Supabase client")

    # Process each table configuration
    for table_name, table_config in TABLES.items():
        # Check if table needs geocoding based on configuration
        if table_config.get("needs_geocoding", False):
            with ExceptionContext(
                f"Processing {table_name} table", DataProcessingError
            ):
                process_db_source(table_config, supabase_client)
        else:
            logging.debug(f"Skipping table {table_name} (does not need geocoding)")

    logging.info("Database-based geocoding process completed successfully")


@handle_exception(
    custom_mapping={
        DataAccessError: DataAccessError,
        APIConnectionError: APIConnectionError,
        Exception: DataProcessingError,
    }
)
@with_log_context(module="geocode", operation="main")
def main():
    """Main function to process geocoding with structured error handling."""
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(
        description="Geocode addresses from database tables or CSV files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Geocode addresses from database tables
  python -m src.geocode --mode use-db

  # Geocode addresses from local CSV files
  python -m src.geocode --mode use-local

For more information, see the module documentation.
""",
    )
    parser.add_argument(
        "--mode",
        choices=["use-db", "use-local"],
        default="use-local",
        help="Processing mode: 'use-db' to fetch and update records in the database, 'use-local' to process CSV files in the locations directory (default: use-db)",
    )

    args = parser.parse_args()

    logging.info(f"Starting geocoding process in {args.mode} mode...")

    if args.mode == "use-local":
        process_csv_mode()
    else:
        process_db_mode()

    logging.info(f"Geocoding process in {args.mode} mode completed successfully")


if __name__ == "__main__":
    main()
