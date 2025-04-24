"""
GeoJSON Utility Functions
======================

This module contains utility functions for working with GeoJSON data, including validation,
creation, manipulation, and processing functions.

Functions:
    validate_geojson: Validate if input is valid GeoJSON.
    create_point: Create a GeoJSON Point feature.
    create_polygon: Create a GeoJSON Polygon feature.
    extract_features: Extract all features from a GeoJSON object.
    find_features_by_property: Find features with matching property.
    get_bbox: Calculate the bounding box for a GeoJSON object.
    merge_feature_collections: Merge two feature collections.
    merge_geojson: Merge multiple GeoJSON objects into a single FeatureCollection.
    process_geojson_batch: Process a batch of GeoJSON files with proper error handling.

Example:
    >>> from src.utils.geojson_utils import validate_geojson, create_point
    >>> point = create_point(lon=-122.4194, lat=37.7749, properties={"name": "San Francisco"})
    >>> is_valid = validate_geojson(point)  # Returns the validated GeoJSON if valid
"""

# Standard library imports
import json
import logging
from typing import Dict, List, Union, Any, Optional

# Local imports
from src.utils.logging_utils import LogContext, with_log_context
from src.utils.error_utils import (
    handle_exception,
    ExceptionContext,
    DataValidationError,
    DataProcessingError,
    GeoJSONError,
)

# GeoJSON Types
VALID_GEOJSON_TYPES = {
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
    "GeometryCollection",
    "Feature",
    "FeatureCollection",
}


@handle_exception(
    custom_mapping={
        json.JSONDecodeError: DataValidationError,
        ValueError: DataValidationError,
        TypeError: DataValidationError,
        Exception: GeoJSONError,
    }
)
@with_log_context(module="geojson_utils", operation="validate_geojson")
def validate_geojson(data: Union[Dict, str]) -> Dict:
    """
    Validate if the input is valid GeoJSON.

    Args:
        data: GeoJSON data as dict or JSON string

    Returns:
        Dict: The validated GeoJSON data

    Raises:
        DataValidationError: If data doesn't follow GeoJSON spec
        GeoJSONError: For other GeoJSON-related errors
    """
    # Parse if string input
    if isinstance(data, str):
        try:
            logging.debug("Parsing JSON string input")
            data = json.loads(data)
        except json.JSONDecodeError as e:
            logging.warning(f"Invalid JSON: {e}")
            raise DataValidationError(f"Invalid JSON: {e}")

    # Must be a dictionary
    if not isinstance(data, dict):
        logging.warning("GeoJSON must be a JSON object")
        raise DataValidationError("GeoJSON must be a JSON object")

    # Must have a type
    if "type" not in data:
        logging.warning("GeoJSON missing required 'type' property")
        raise DataValidationError("GeoJSON must have a 'type' property")

    # Type must be valid
    if data["type"] not in VALID_GEOJSON_TYPES:
        logging.warning(f"Invalid GeoJSON type: {data['type']}")
        raise DataValidationError(f"Invalid GeoJSON type: {data['type']}")

    # Validate based on type
    with LogContext(geojson_type=data["type"]):
        logging.debug(f"Validating {data['type']} object")

        if data["type"] == "Feature":
            _validate_feature(data)
        elif data["type"] == "FeatureCollection":
            _validate_feature_collection(data)
        elif data["type"] == "GeometryCollection":
            _validate_geometry_collection(data)
        else:
            _validate_geometry(data)

    logging.info("GeoJSON validation successful")
    return data


def _validate_coordinates(coords, dimension):
    """Validate coordinates based on geometry dimension."""
    with LogContext(coord_dimension=dimension):
        if dimension == 0:  # Point
            if not isinstance(coords, list) or len(coords) < 2:
                logging.warning("Invalid point coordinates")
                raise DataValidationError(
                    "Point coordinates must be an array of at least 2 numbers"
                )
        elif dimension == 1:  # LineString or MultiPoint
            if not isinstance(coords, list):
                logging.warning("Invalid LineString/MultiPoint coordinates")
                raise DataValidationError(
                    "LineString/MultiPoint must be an array of positions"
                )
            for i, point in enumerate(coords):
                with LogContext(point_idx=i):
                    _validate_coordinates(point, 0)
        elif dimension == 2:  # Polygon or MultiLineString
            if not isinstance(coords, list):
                logging.warning("Invalid Polygon/MultiLineString coordinates")
                raise DataValidationError(
                    "Polygon/MultiLineString must be an array of line arrays"
                )
            for i, line in enumerate(coords):
                with LogContext(line_idx=i):
                    _validate_coordinates(line, 1)
        elif dimension == 3:  # MultiPolygon
            if not isinstance(coords, list):
                logging.warning("Invalid MultiPolygon coordinates")
                raise DataValidationError(
                    "MultiPolygon must be an array of polygon arrays"
                )
            for i, polygon in enumerate(coords):
                with LogContext(polygon_idx=i):
                    _validate_coordinates(polygon, 2)


def _validate_geometry(geometry):
    """Validate a GeoJSON geometry object."""
    if "coordinates" not in geometry:
        logging.warning("Geometry missing 'coordinates' property")
        raise DataValidationError("Geometry must have 'coordinates' property")

    geom_type = geometry["type"]
    coords = geometry["coordinates"]

    # Validate coordinates based on geometry type
    with LogContext(geometry_type=geom_type):
        logging.debug(f"Validating {geom_type} coordinates")
        if geom_type == "Point":
            _validate_coordinates(coords, 0)
        elif geom_type in ("LineString", "MultiPoint"):
            _validate_coordinates(coords, 1)
        elif geom_type in ("Polygon", "MultiLineString"):
            _validate_coordinates(coords, 2)
        elif geom_type == "MultiPolygon":
            _validate_coordinates(coords, 3)


def _validate_feature(feature):
    """Validate a GeoJSON Feature object."""
    if "geometry" not in feature:
        logging.warning("Feature missing 'geometry' property")
        raise DataValidationError("Feature must have a 'geometry' property")

    # Geometry can be null
    if feature["geometry"] is not None:
        # Validate geometry
        if not isinstance(feature["geometry"], dict):
            logging.warning("Feature geometry is not an object")
            raise DataValidationError(
                "Feature geometry must be a GeoJSON geometry object"
            )

        # Validate the geometry
        logging.debug("Validating feature geometry")
        _validate_geometry(feature["geometry"])

    # Properties can be null or an object
    if "properties" in feature and feature["properties"] is not None:
        if not isinstance(feature["properties"], dict):
            logging.warning("Feature properties is not an object")
            raise DataValidationError("Feature properties must be an object")

    logging.debug("Feature validation successful")


def _validate_feature_collection(fc):
    """Validate a GeoJSON FeatureCollection."""
    if "features" not in fc:
        logging.warning("FeatureCollection missing 'features' property")
        raise DataValidationError("FeatureCollection must have a 'features' property")

    if not isinstance(fc["features"], list):
        logging.warning("FeatureCollection 'features' is not an array")
        raise DataValidationError("FeatureCollection 'features' must be an array")

    for i, feature in enumerate(fc["features"]):
        with LogContext(feature_idx=i):
            logging.debug(f"Validating feature {i}")
            _validate_feature(feature)

    logging.debug(f"FeatureCollection with {len(fc['features'])} features validated")


def _validate_geometry_collection(gc):
    """Validate a GeoJSON GeometryCollection."""
    if "geometries" not in gc:
        logging.warning("GeometryCollection missing 'geometries' property")
        raise DataValidationError(
            "GeometryCollection must have a 'geometries' property"
        )

    if not isinstance(gc["geometries"], list):
        logging.warning("GeometryCollection 'geometries' is not an array")
        raise DataValidationError("GeometryCollection 'geometries' must be an array")

    for i, geometry in enumerate(gc["geometries"]):
        with LogContext(geometry_idx=i):
            logging.debug(f"Validating geometry {i}")
            _validate_geometry(geometry)

    logging.debug(
        f"GeometryCollection with {len(gc['geometries'])} geometries validated"
    )


# Helper functions
@handle_exception(
    custom_mapping={ValueError: DataValidationError, Exception: GeoJSONError}
)
@with_log_context(module="geojson_utils", operation="create_point")
def create_point(lon: float, lat: float, properties: Optional[Dict] = None) -> Dict:
    """
    Create a GeoJSON Point feature.

    Args:
        lon: Longitude coordinate
        lat: Latitude coordinate
        properties: Optional properties dictionary

    Returns:
        Dict: A GeoJSON Point feature

    Raises:
        DataValidationError: If coordinates are invalid
        GeoJSONError: For other GeoJSON-related errors
    """
    logging.debug(f"Creating point at lon: {lon}, lat: {lat}")
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": properties or {},
    }
    logging.info("Point feature created successfully")
    return feature


@handle_exception(
    custom_mapping={ValueError: DataValidationError, Exception: GeoJSONError}
)
@with_log_context(module="geojson_utils", operation="create_polygon")
def create_polygon(
    coordinates: List[List[List[float]]], properties: Optional[Dict] = None
) -> Dict:
    """
    Create a GeoJSON Polygon feature.

    Args:
        coordinates: Array of linear rings
        properties: Optional properties dictionary

    Returns:
        Dict: A GeoJSON Polygon feature

    Raises:
        DataValidationError: If coordinates are invalid
        GeoJSONError: For other GeoJSON-related errors
    """
    if not coordinates or not isinstance(coordinates, list):
        logging.warning("Invalid polygon coordinates")
        raise DataValidationError("Polygon coordinates must be a non-empty array")

    logging.debug(f"Creating polygon with {len(coordinates)} rings")
    feature = {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": coordinates},
        "properties": properties or {},
    }
    logging.info("Polygon feature created successfully")
    return feature


@handle_exception(custom_mapping={Exception: DataProcessingError})
@with_log_context(module="geojson_utils", operation="extract_features")
def extract_features(geojson: Dict) -> List[Dict]:
    """
    Extract all features from a GeoJSON object.

    Args:
        geojson: Any GeoJSON object

    Returns:
        List[Dict]: Array of GeoJSON features

    Raises:
        DataProcessingError: If feature extraction fails
    """
    with LogContext(geojson_type=geojson.get("type")):
        logging.debug(
            f"Extracting features from {geojson.get('type', 'unknown')} object"
        )

        if geojson["type"] == "FeatureCollection":
            features = geojson["features"]
            logging.info(f"Extracted {len(features)} features from FeatureCollection")
            return features
        elif geojson["type"] == "Feature":
            logging.info("Extracted single Feature")
            return [geojson]
        else:
            # Create a feature from a geometry
            logging.info(f"Created feature from {geojson['type']} geometry")
            return [{"type": "Feature", "geometry": geojson, "properties": {}}]


@handle_exception(
    custom_mapping={KeyError: DataValidationError, Exception: DataProcessingError}
)
@with_log_context(module="geojson_utils", operation="find_features_by_property")
def find_features_by_property(geojson: Dict, key: str, value: Any) -> List[Dict]:
    """
    Find features with matching property.

    Args:
        geojson: Any GeoJSON object
        key: Property key to match
        value: Property value to match

    Returns:
        List[Dict]: Array of matching features

    Raises:
        DataValidationError: If input is invalid
        DataProcessingError: If feature search fails
    """
    with LogContext(property_key=key, property_value=str(value)):
        logging.debug(f"Searching for features with {key}={value}")

        features = extract_features(geojson)
        matched_features = [
            feature
            for feature in features
            if feature.get("properties") and feature["properties"].get(key) == value
        ]

        logging.info(f"Found {len(matched_features)} features matching {key}={value}")
        return matched_features


@handle_exception(
    custom_mapping={ValueError: DataValidationError, Exception: DataProcessingError}
)
@with_log_context(module="geojson_utils", operation="get_bbox")
def get_bbox(geojson: Dict) -> List[float]:
    """
    Calculate the bounding box for a GeoJSON object.

    Args:
        geojson: Any GeoJSON object

    Returns:
        List[float]: [min_lon, min_lat, max_lon, max_lat]

    Raises:
        DataValidationError: If input is invalid
        DataProcessingError: If bbox calculation fails
    """
    logging.debug("Calculating bounding box")
    min_lon, min_lat = float("inf"), float("inf")
    max_lon, max_lat = float("-inf"), float("-inf")

    def update_bounds(lon, lat):
        nonlocal min_lon, min_lat, max_lon, max_lat
        min_lon = min(min_lon, lon)
        min_lat = min(min_lat, lat)
        max_lon = max(max_lon, lon)
        max_lat = max(max_lat, lat)

    def process_coords(coords, dim=0):
        if dim == 0:  # Point
            update_bounds(coords[0], coords[1])
        elif dim == 1:  # LineString/MultiPoint
            for point in coords:
                process_coords(point, 0)
        elif dim == 2:  # Polygon/MultiLineString
            for line in coords:
                process_coords(line, 1)
        elif dim == 3:  # MultiPolygon
            for polygon in coords:
                process_coords(polygon, 2)

    features = extract_features(geojson)
    for i, feature in enumerate(features):
        with LogContext(feature_idx=i):
            if feature["geometry"] is None:
                logging.debug("Skipping feature with null geometry")
                continue

            geom_type = feature["geometry"]["type"]
            coords = feature["geometry"]["coordinates"]

            logging.debug(f"Processing {geom_type} coordinates")
            if geom_type == "Point":
                process_coords(coords, 0)
            elif geom_type in ("LineString", "MultiPoint"):
                process_coords(coords, 1)
            elif geom_type in ("Polygon", "MultiLineString"):
                process_coords(coords, 2)
            elif geom_type == "MultiPolygon":
                process_coords(coords, 3)

    bbox = [min_lon, min_lat, max_lon, max_lat]
    logging.info(f"Calculated bounding box: {bbox}")
    return bbox


@handle_exception(
    custom_mapping={ValueError: DataValidationError, Exception: DataProcessingError}
)
@with_log_context(module="geojson_utils", operation="merge_feature_collections")
def merge_feature_collections(fc1: Dict, fc2: Dict) -> Dict:
    """
    Merge two feature collections.

    Args:
        fc1: First FeatureCollection
        fc2: Second FeatureCollection

    Returns:
        Dict: Merged FeatureCollection

    Raises:
        DataValidationError: If inputs are not valid FeatureCollections
        DataProcessingError: If merging fails
    """
    # Validate both are feature collections
    if fc1["type"] != "FeatureCollection" or fc2["type"] != "FeatureCollection":
        logging.warning("Inputs are not both FeatureCollections")
        raise DataValidationError("Both inputs must be FeatureCollections")

    logging.info(
        f"Merging FeatureCollections with {len(fc1['features'])} and {len(fc2['features'])} features"
    )

    # Create a new feature collection with merged features
    result = {
        "type": "FeatureCollection",
        "features": fc1["features"] + fc2["features"],
    }
    logging.info(
        f"Created merged FeatureCollection with {len(result['features'])} features"
    )
    return result


@handle_exception(
    custom_mapping={ValueError: DataValidationError, Exception: DataProcessingError}
)
@with_log_context(module="geojson_utils", operation="merge_geojson")
def merge_geojson(geojson_objects: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge multiple GeoJSON objects into a single FeatureCollection.

    Args:
        geojson_objects: List of GeoJSON objects to merge

    Returns:
        dict: A FeatureCollection containing all features

    Raises:
        DataValidationError: If inputs are invalid
        DataProcessingError: If merging fails
    """
    logging.info(f"Merging {len(geojson_objects)} GeoJSON objects")
    features = []

    # Process each GeoJSON object
    for i, geojson in enumerate(geojson_objects):
        with LogContext(geojson_idx=i):
            # Using ExceptionContext for this specific operation
            with ExceptionContext(
                f"Validating GeoJSON object {i}", DataValidationError
            ):
                # Validate the GeoJSON - using context manager instead of try/except
                validated_geojson = validate_geojson(geojson)

            # Extract features based on GeoJSON type
            if validated_geojson["type"] == "FeatureCollection":
                features.extend(validated_geojson["features"])
                logging.debug(
                    f"Added {len(validated_geojson['features'])} features from FeatureCollection"
                )

            elif validated_geojson["type"] == "Feature":
                features.append(validated_geojson)
                logging.debug("Added single Feature")

            else:
                # Convert geometry to feature
                feature = {
                    "type": "Feature",
                    "geometry": validated_geojson,
                    "properties": {},
                }
                features.append(feature)
                logging.debug(
                    f"Converted {validated_geojson['type']} geometry to Feature"
                )

    # Create the merged FeatureCollection
    merged_geojson = {"type": "FeatureCollection", "features": features}

    logging.info(f"Successfully merged {len(features)} features")
    return merged_geojson


def process_geojson_batch(
    batch_files: List[str], output_format: str = "geojson"
) -> Union[Dict, List]:
    """
    Process a batch of GeoJSON files with proper error handling.

    Args:
        batch_files: List of file paths to process
        output_format: Output format, either 'geojson' or 'features'

    Returns:
        Union[Dict, List]: Either a FeatureCollection or list of features

    Raises:
        DataProcessingError: If batch processing fails
    """
    logging.info(f"Processing batch of {len(batch_files)} GeoJSON files")
    all_geojson = []

    # Using ExceptionContext for the entire batch operation
    with ExceptionContext("GeoJSON batch processing", DataProcessingError):
        for i, file_path in enumerate(batch_files):
            with LogContext(file_idx=i, file_path=file_path):
                logging.debug(f"Processing file {i}: {file_path}")

                # Load the file
                try:
                    with open(file_path, "r") as f:
                        content = f.read()

                    # Validate GeoJSON - if invalid, this will raise an exception
                    # that will be caught by the ExceptionContext
                    geojson = validate_geojson(content)
                    all_geojson.append(geojson)
                    logging.info(f"Successfully processed file {file_path}")
                except Exception as e:
                    # Log but continue with other files
                    logging.warning(f"Failed to process file {file_path}: {e}")
                    continue

    # Merge all valid GeoJSON objects
    if not all_geojson:
        logging.warning("No valid GeoJSON files in batch")
        return {"type": "FeatureCollection", "features": []}

    result = merge_geojson(all_geojson)

    # Return either the full GeoJSON or just the features
    if output_format == "features":
        return result["features"]
    return result
