import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from shapely.geometry import Polygon
from shapely.geometry import mapping

from src.utils.data_utils import load_data, load_isochrones
from src.utils.error_utils import DataAccessError, DataValidationError


class TestDataUtils(unittest.TestCase):
    def setUp(self):
        # Common setup for tests
        self.mock_supabase = MagicMock()
        self.mock_table = MagicMock()
        self.mock_select = MagicMock()
        self.mock_execute = MagicMock()

        # Setup mock chain
        self.mock_supabase.table.return_value = self.mock_table
        self.mock_table.select.return_value = self.mock_select
        self.mock_select.execute.return_value = self.mock_execute

    def test_load_data_success(self):
        # Setup mock response
        test_data = [
            {"id": 1, "name": "Test 1", "value": 10},
            {"id": 2, "name": "Test 2", "value": 20},
        ]
        self.mock_execute.data = test_data

        # Execute
        result = load_data(self.mock_supabase, "test_table")

        # Assert
        self.mock_supabase.table.assert_called_once_with("test_table")
        self.mock_table.select.assert_called_once_with("*")
        self.mock_select.execute.assert_called_once()

        # Check result
        pd.testing.assert_frame_equal(result, pd.DataFrame(test_data))

    def test_load_data_with_dtype(self):
        # Setup mock response
        test_data = [
            {"id": "1", "name": "Test 1", "value": "10"},
            {"id": "2", "name": "Test 2", "value": "20"},
        ]
        self.mock_execute.data = test_data

        # Custom dtype
        dtype = {"id": int, "value": int}

        # Execute
        result = load_data(self.mock_supabase, "test_table", dtype=dtype)

        # Assert function calls
        self.mock_supabase.table.assert_called_once_with("test_table")

        # Check result has correct types
        expected_df = pd.DataFrame(test_data).astype(dtype)
        pd.testing.assert_frame_equal(result, expected_df)
        self.assertEqual(result["id"].dtype, "int64")
        self.assertEqual(result["value"].dtype, "int64")

    def test_load_data_exception(self):
        # Setup mock to raise exception
        self.mock_select.execute.side_effect = Exception("Database connection error")

        # Execute & Assert
        with self.assertRaises(DataAccessError) as context:
            load_data(self.mock_supabase, "test_table")

        self.assertIn("Database connection error", str(context.exception))

    def test_load_isochrones_success(self):
        # Setup mock response with WKB geometry
        # Create a simple polygon for testing
        polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        wkb_hex = polygon.wkb_hex

        test_data = [
            {
                "name": "Isochrone 1",
                "value": 10,
                "geom": wkb_hex,
                "metadata": {"color": "red", "opacity": 0.5},
            },
            {
                "name": "Isochrone 2",
                "value": 20,
                "geom": wkb_hex,
                "metadata": {"color": "blue", "opacity": 0.7},
            },
        ]
        self.mock_execute.data = test_data

        # Mock tables config
        tables_config = {
            "isochrones": {
                "table_name": "isochrones",
                "columns": {
                    "name": "name",
                    "value": "value",
                    "geometry": "geom",
                    "metadata": "metadata",
                },
            }
        }

        # Execute
        result = load_isochrones(self.mock_supabase, tables_config)

        # Assert
        self.mock_supabase.table.assert_called_once_with("isochrones")
        self.mock_table.select.assert_called_once_with("name, value, geom, metadata")

        # Check result is a proper GeoJSON
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertEqual(len(result["features"]), 2)

        # Check first feature
        feature1 = result["features"][0]
        self.assertEqual(feature1["type"], "Feature")
        self.assertEqual(feature1["properties"]["name"], "Isochrone 1")
        self.assertEqual(feature1["properties"]["value"], 10)
        self.assertEqual(feature1["properties"]["color"], "red")
        self.assertEqual(feature1["geometry"], mapping(polygon))

    def test_load_isochrones_empty_response(self):
        # Setup mock with empty response
        self.mock_execute.data = []

        tables_config = {
            "isochrones": {
                "table_name": "isochrones",
                "columns": {
                    "name": "name",
                    "value": "value",
                    "geometry": "geom",
                    "metadata": "metadata",
                },
            }
        }

        # Execute & Assert
        with self.assertRaises(DataValidationError) as context:
            load_isochrones(self.mock_supabase, tables_config)

        self.assertIn("No isochrone data found", str(context.exception))

    def test_load_isochrones_invalid_geometry(self):
        # Setup mock with invalid geometry
        test_data = [
            {
                "name": "Invalid Isochrone",
                "value": 10,
                "geom": "not_valid_wkb_hex",
                "metadata": {"color": "red"},
            },
            {
                "name": "Valid Isochrone",
                "value": 20,
                "geom": Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]).wkb_hex,
                "metadata": {"color": "blue"},
            },
        ]
        self.mock_execute.data = test_data

        tables_config = {
            "isochrones": {
                "table_name": "isochrones",
                "columns": {
                    "name": "name",
                    "value": "value",
                    "geometry": "geom",
                    "metadata": "metadata",
                },
            }
        }

        # Execute with patch to prevent logging errors in test output
        with patch("src.utils.data_utils.logging"):
            result = load_isochrones(self.mock_supabase, tables_config)

        # Only valid geometry should be included
        self.assertEqual(len(result["features"]), 1)
        self.assertEqual(result["features"][0]["properties"]["name"], "Valid Isochrone")

    def test_load_isochrones_exception(self):
        # Setup mock to raise exception
        self.mock_select.execute.side_effect = Exception("Database error")

        tables_config = {
            "isochrones": {
                "table_name": "isochrones",
                "columns": {
                    "name": "name",
                    "value": "value",
                    "geometry": "geom",
                    "metadata": "metadata",
                },
            }
        }

        # Execute & Assert with patch to prevent logging errors in test output
        with patch("src.utils.data_utils.logging"), self.assertRaises(
            DataAccessError
        ) as context:
            load_isochrones(self.mock_supabase, tables_config)

        self.assertIn("Database error", str(context.exception))
