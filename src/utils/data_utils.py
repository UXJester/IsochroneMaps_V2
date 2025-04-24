"""
Data Utility Functions
=====================

This module contains utility functions for loading and processing data from Supabase.

Functions:
    load_data: Load data from a Supabase table into a pandas DataFrame.
    load_isochrones: Load isochrone data from Supabase and convert to GeoJSON format.

Example:
    >>> from src.utils.data_utils import load_data
    >>> data = load_data(supabase_client, "my_table")
    >>> print(f"Loaded {len(data)} rows")
"""

# Standard library imports
import logging

# Third-party imports
import pandas as pd
from shapely import wkb
from shapely.geometry import mapping
from supabase import Client

# Local imports
from src.utils.error_utils import (
    handle_exception,
    DataAccessError,
    DataProcessingError,
    DataValidationError,
    GeoJSONError,
)
from src.utils.logging_utils import LogContext, with_log_context


@handle_exception(custom_mapping={Exception: DataAccessError})
@with_log_context(module="data_utils", operation="load_data")
def load_data(supabase: Client, table_name: str, dtype=None) -> pd.DataFrame:
    """
    Load and prepare data from a Supabase table.

    Args:
        supabase (Client): The Supabase client instance.
        table_name (str): The name of the table to query.
        dtype (dict, optional): A dictionary specifying column data types.

    Returns:
        pd.DataFrame: A pandas DataFrame containing the table data.

    Raises:
        DataAccessError: If the data cannot be loaded from Supabase.
    """
    # Query the table from Supabase
    logging.info(f"Loading data from table: {table_name}")
    response = supabase.table(table_name).select("*").execute()

    # Convert the data to a pandas DataFrame
    data = pd.DataFrame(response.data)  # Access the data attribute directly
    logging.info(f"Successfully loaded {len(data)} rows from {table_name}")

    # Optionally cast columns to specific data types
    if dtype:
        try:
            logging.debug(f"Applying data type conversions: {dtype}")
            data = data.astype(dtype)
        except Exception as e:
            logging.warning(f"Failed to apply data type conversions: {e}")
            raise DataProcessingError(f"Failed to apply data type conversions: {e}")

    return data


@handle_exception(
    custom_mapping={
        ValueError: DataValidationError,
        KeyError: DataValidationError,
        Exception: DataAccessError,
    }
)
@with_log_context(module="data_utils", operation="load_isochrones")
def load_isochrones(supabase: Client, tables_config: dict) -> dict:
    """
    Load and prepare isochrone data from a Supabase table.

    Args:
        supabase (Client): The Supabase client instance.
        tables_config (dict): The TABLES configuration dictionary.

    Returns:
        dict: A GeoJSON-like dictionary containing isochrone features.

    Raises:
        DataAccessError: If the data cannot be loaded from Supabase.
        DataValidationError: If the data is missing or invalid.
        DataProcessingError: If the data cannot be processed.
        GeoJSONError: If there's an issue with GeoJSON conversion.
    """
    # Dynamically get table name and column mappings from config
    if "isochrones" not in tables_config:
        logging.error("Missing isochrones configuration")
        raise DataValidationError("Missing isochrones configuration in tables_config")

    isochrones_table = tables_config["isochrones"]["table_name"]
    columns = tables_config["isochrones"]["columns"]

    logging.info(f"Loading isochrone data from table: {isochrones_table}")

    # Query the "isochrones" table from Supabase
    response = (
        supabase.table(isochrones_table)
        .select(
            f"{columns['name']}, {columns['value']}, {columns['geometry']}, {columns['metadata']}"
        )
        .execute()
    )

    # Ensure the response contains data
    if not response.data:
        logging.warning(f"No isochrone data found in table: {isochrones_table}")
        raise DataValidationError(
            f"No isochrone data found in table: {isochrones_table}"
        )

    logging.info(f"Processing {len(response.data)} isochrone features")

    # Convert the data into GeoJSON-like format
    isochrones_features = []
    geometry_errors = 0

    for i, row in enumerate(response.data):
        with LogContext(feature_idx=i, feature_name=row[columns["name"]]):
            geometry_raw = row[columns["geometry"]]
            logging.debug("Processing geometry data")

            # Validate and convert the geometry field
            try:
                # Attempt to parse as WKB
                geometry = wkb.loads(bytes.fromhex(geometry_raw))
                geometry_geojson = mapping(geometry)  # Convert to GeoJSON
            except ValueError as ve:
                geometry_errors += 1
                logging.warning(f"Invalid geometry format: {ve}")
                continue
            except Exception as parse_error:
                geometry_errors += 1
                logging.warning(f"Error processing geometry: {parse_error}")
                continue

            try:
                properties = {
                    "name": row[columns["name"]],
                    "value": row[columns["value"]],
                    **row[columns["metadata"]],  # Include metadata
                }

                isochrones_features.append(
                    {
                        "type": "Feature",
                        "geometry": geometry_geojson,
                        "properties": properties,
                    }
                )
            except Exception as e:
                logging.warning(f"Failed to create feature: {e}")
                raise DataProcessingError(f"Failed to create feature from row {i}: {e}")

    # If all geometries failed, raise a more specific error
    if geometry_errors > 0 and len(isochrones_features) == 0:
        logging.error(f"All {geometry_errors} geometries failed to process")
        raise GeoJSONError("Failed to process any geometries to GeoJSON format")

    if geometry_errors > 0:
        logging.warning(f"Skipped {geometry_errors} invalid geometries")

    logging.info(
        f"Successfully processed {len(isochrones_features)} valid isochrone features"
    )
    return {"type": "FeatureCollection", "features": isochrones_features}
