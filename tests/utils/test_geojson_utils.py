import unittest
from unittest import mock
from src.utils.geojson_utils import (
    validate_geojson,
    create_point,
    create_polygon,
    extract_features,
    find_features_by_property,
    get_bbox,
    merge_feature_collections,
    merge_geojson,
    process_geojson_batch,
    DataValidationError,
    GeoJSONError,
)


class TestGeoJSONUtils(unittest.TestCase):
    def test_validate_valid_point(self):
        point = {"type": "Point", "coordinates": [125.6, 10.1]}
        self.assertEqual(validate_geojson(point), point)

    def test_validate_invalid_point(self):
        point = {"type": "Point", "coordinates": "invalid"}
        with self.assertRaises(DataValidationError):
            validate_geojson(point)

    def test_validate_feature(self):
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [125.6, 10.1]},
            "properties": {"name": "Test Point"},
        }
        self.assertEqual(validate_geojson(feature), feature)

    def test_create_point(self):
        point = create_point(125.6, 10.1, {"name": "Test Point"})
        self.assertEqual(point["type"], "Feature")
        self.assertEqual(point["geometry"]["type"], "Point")
        self.assertEqual(point["geometry"]["coordinates"], [125.6, 10.1])
        self.assertEqual(point["properties"]["name"], "Test Point")

    def test_create_polygon(self):
        polygon = create_polygon(
            [[[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]]],
            {"name": "Test Polygon"},
        )
        self.assertEqual(polygon["type"], "Feature")
        self.assertEqual(polygon["geometry"]["type"], "Polygon")
        self.assertEqual(
            polygon["geometry"]["coordinates"],
            [[[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]]],
        )
        self.assertEqual(polygon["properties"]["name"], "Test Polygon")

    def test_extract_features(self):
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {},
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [1, 1]},
                    "properties": {},
                },
            ],
        }
        features = extract_features(geojson)
        self.assertEqual(len(features), 2)
        self.assertEqual(features[0]["geometry"]["coordinates"], [0, 0])
        self.assertEqual(features[1]["geometry"]["coordinates"], [1, 1])

    def test_find_features_by_property(self):
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"id": 1},
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [1, 1]},
                    "properties": {"id": 2},
                },
            ],
        }
        matching_features = find_features_by_property(geojson, "id", 1)
        self.assertEqual(len(matching_features), 1)
        self.assertEqual(matching_features[0]["properties"]["id"], 1)

    def test_get_bbox(self):
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {},
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [1, 1]},
                    "properties": {},
                },
            ],
        }
        bbox = get_bbox(geojson)
        self.assertEqual(bbox, [0, 0, 1, 1])

    def test_merge_feature_collections(self):
        fc1 = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"id": 1},
                },
            ],
        }
        fc2 = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [1, 1]},
                    "properties": {"id": 2},
                },
            ],
        }
        merged = merge_feature_collections(fc1, fc2)
        self.assertEqual(len(merged["features"]), 2)
        self.assertEqual(merged["features"][0]["properties"]["id"], 1)
        self.assertEqual(merged["features"][1]["properties"]["id"], 2)

    def test_merge_geojson(self):
        geojson1 = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {"id": 1},
        }
        geojson2 = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [1, 1]},
            "properties": {"id": 2},
        }
        merged = merge_geojson([geojson1, geojson2])
        self.assertEqual(merged["type"], "FeatureCollection")
        self.assertEqual(len(merged["features"]), 2)
        self.assertEqual(merged["features"][0]["properties"]["id"], 1)
        self.assertEqual(merged["features"][1]["properties"]["id"], 2)

    def test_invalid_geojson_type_raises_data_validation_error(self):
        """Test that invalid GeoJSON structure raises DataValidationError."""
        # Create an invalid GeoJSON with unknown type
        # According to implementation, invalid type raises DataValidationError, not GeoJSONError
        invalid_geojson = {"type": "Unknown", "coordinates": [0, 0]}
        with self.assertRaises(DataValidationError):
            validate_geojson(invalid_geojson)

    def test_general_exception_raises_geojson_error(self):
        """Test that a general exception in validate_geojson gets mapped to GeoJSONError."""
        # Create a mock that raises a general Exception when called
        with mock.patch(
            "src.utils.geojson_utils._validate_geometry",
            side_effect=Exception("General error"),
        ):
            test_geojson = {"type": "Point", "coordinates": [0, 0]}
            with self.assertRaises(GeoJSONError):
                validate_geojson(test_geojson)

    @mock.patch("json.loads")
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    def test_process_geojson_batch(self, mock_open, mock_json_loads):
        """Test processing a batch of GeoJSON files."""
        # Setup mock for file reading
        mock_file_data = '{"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, 0]}, "properties": {"id": 1}}'
        mock_open.return_value.__enter__.return_value.read.return_value = mock_file_data

        # Setup parsed JSON data
        file1_geojson = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {"id": 1},
        }
        file2_geojson = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [1, 1]},
            "properties": {"id": 2},
        }

        # Mock json.loads to return our test data
        mock_json_loads.side_effect = [file1_geojson, file2_geojson]

        # Setup temporary files
        test_files = ["file1.geojson", "file2.geojson"]

        # Test the function - the actual implementation will call json.loads internally
        result = process_geojson_batch(test_files)

        # Assertions
        self.assertEqual(result["type"], "FeatureCollection")
        # Check that mock_open was called with each file path
        mock_open.assert_any_call("file1.geojson", "r")
        mock_open.assert_any_call("file2.geojson", "r")
        self.assertEqual(mock_open.call_count, 2)

        # Test with output_format="features"
        mock_json_loads.side_effect = [file1_geojson, file2_geojson]
        mock_open.reset_mock()

        result_features = process_geojson_batch(test_files, output_format="features")
        self.assertIsInstance(result_features, list)
        self.assertEqual(len(result_features), 2)
