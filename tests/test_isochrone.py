import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import pandas as pd
import json
from pathlib import Path

# Add the project root to path to allow importing from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.isochrone import (
    load_center_data,
    generate_isochrone,
    upsert_isochrones,
    check_existing_isochrones,
    save_geojson_file,
    main,
)
from src.utils.error_utils import (
    DataAccessError,
    DataValidationError,
    APIConnectionError,
    DataProcessingError,
    GeoJSONError,
)


class TestIsochrone(unittest.TestCase):
    """Test suite for isochrone.py module"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Sample centers DataFrame
        self.centers_df = pd.DataFrame(
            {
                "id": [1, 2],
                "name": ["Test City 1", "Test City 2"],
                "state": ["CA", "NY"],
                "zip_code": ["94105", "10001"],
                "latitude": [37.7749, 40.7128],
                "longitude": [-122.4194, -74.006],
            }
        )

        # Sample isochrone GeoJSON response
        self.isochrone_result = {
            "type": "FeatureCollection",
            "metadata": {"timestamp": "2023-01-01T12:00:00Z"},
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "group_index": 0,
                        "value": 3600,  # 60 minutes
                        "center": [-122.4194, 37.7749],
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-122.4194, 37.7749],
                                [-122.4294, 37.7849],
                                [-122.4394, 37.7749],
                                [-122.4294, 37.7649],
                                [-122.4194, 37.7749],
                            ]
                        ],
                    },
                },
                {
                    "type": "Feature",
                    "properties": {
                        "group_index": 0,
                        "value": 1800,  # 30 minutes
                        "center": [-122.4194, 37.7749],
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-122.4194, 37.7749],
                                [-122.4244, 37.7799],
                                [-122.4294, 37.7749],
                                [-122.4244, 37.7699],
                                [-122.4194, 37.7749],
                            ]
                        ],
                    },
                },
            ],
        }

        # Mock supabase responses
        self.mock_supabase_response = MagicMock()
        self.mock_supabase_response.data = [{"id": 1}]

        # Configure paths
        self.mock_config_patcher = patch(
            "src.isochrone.TABLES",
            {
                "centers": {
                    "table_name": "centers",
                    "columns": {
                        "id": "id",
                        "city": "name",
                        "state": "state",
                        "zip_code": "zip_code",
                        "latitude": "latitude",
                        "longitude": "longitude",
                    },
                },
                "isochrones": {
                    "table_name": "isochrones",
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
            },
        )
        self.mock_config = self.mock_config_patcher.start()

        self.mock_locations_patcher = patch(
            "src.isochrone.LOCATIONS", "/mock/locations/path"
        )
        self.mock_locations = self.mock_locations_patcher.start()

        self.mock_isochrones_patcher = patch(
            "src.isochrone.ISOCHRONES", "/mock/isochrones/path"
        )
        self.mock_isochrones = self.mock_isochrones_patcher.start()

    def tearDown(self):
        """Clean up after each test method."""
        self.mock_config_patcher.stop()
        self.mock_locations_patcher.stop()
        self.mock_isochrones_patcher.stop()
        patch.stopall()

    @patch("pandas.read_csv")
    def test_load_center_data_local(self, mock_read_csv):
        """Test loading center data from local CSV file"""
        mock_read_csv.return_value = self.centers_df

        with patch("pathlib.Path.exists", return_value=True):
            centers_df, coords_list = load_center_data(mode="use-local")

            self.assertEqual(len(centers_df), 2)
            self.assertEqual(coords_list[0], [-122.4194, 37.7749])
            self.assertEqual(coords_list[1], [-74.006, 40.7128])
            self.assertEqual(len(coords_list), 2)

    @patch("src.isochrone.load_data")
    def test_load_center_data_db(self, mock_load_data):
        """Test loading center data from database"""
        mock_supabase = MagicMock()
        mock_load_data.return_value = self.centers_df
        centers_df, coords_list = load_center_data(mock_supabase, "use-db")
        self.assertEqual(len(centers_df), 2)
        self.assertEqual(coords_list[0], [-122.4194, 37.7749])
        self.assertEqual(coords_list[1], [-74.006, 40.7128])
        self.assertEqual(len(coords_list), 2)
        mock_load_data.assert_called_once_with(
            mock_supabase, "centers", dtype={"id": "int"}
        )

    @patch("src.isochrone.load_data")
    def test_load_center_data_empty(self, mock_load_data):
        """Test loading center data when the data source is empty"""
        mock_load_data.return_value = pd.DataFrame()
        mock_supabase = MagicMock()
        with self.assertRaises(DataValidationError):
            load_center_data(mock_supabase, "use-db")

    @patch("src.isochrone.load_data")
    def test_load_center_data_missing_coordinates(self, mock_load_data):
        """Test loading center data with missing coordinates"""
        centers_with_nan = self.centers_df.copy()
        centers_with_nan.at[0, "latitude"] = None
        mock_load_data.return_value = centers_with_nan
        mock_supabase = MagicMock()
        with self.assertRaises(DataValidationError):
            load_center_data(mock_supabase, "use-db")

    @patch("src.isochrone.isochrones")
    def test_generate_isochrone(self, mock_isochrones):
        """Test successful generation of isochrones"""
        mock_isochrones.return_value = self.isochrone_result
        mock_client = MagicMock()
        center_name, result = generate_isochrone(
            mock_client, -122.4194, 37.7749, "Test City"
        )
        self.assertEqual(center_name, "Test City")
        self.assertEqual(result, self.isochrone_result)
        mock_isochrones.assert_called_once_with(
            mock_client,
            locations=[[-122.4194, 37.7749]],
            profile="driving-car",
            range=[3600, 1800],
            range_type="time",
            smoothing=25,
        )

    @patch("src.isochrone.isochrones")
    def test_generate_isochrone_failure(self, mock_isochrones):
        """Test handling of isochrone generation failure"""
        mock_isochrones.side_effect = Exception("API Error")
        mock_client = MagicMock()
        with self.assertRaises(APIConnectionError):
            generate_isochrone(mock_client, -122.4194, 37.7749, "Test City")

    def test_upsert_isochrones_validation(self):
        """Test validation in upsert_isochrones"""
        mock_supabase = MagicMock()
        with self.assertRaises(DataValidationError):
            upsert_isochrones(
                mock_supabase, "Unknown City", self.isochrone_result, False, None
            )

    @patch("src.isochrone.isochrones")
    def test_upsert_isochrones_dry_run(self, mock_isochrones):
        """Test dry run mode of upsert_isochrones"""
        mock_supabase = MagicMock()
        mock_query = MagicMock()
        mock_execute = MagicMock()
        mock_supabase.table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute.return_value = mock_execute
        mock_execute.data = []
        upsert_isochrones(
            mock_supabase,
            "Test City 1",
            self.isochrone_result,
            dry_run=True,
            centers_df=self.centers_df,
        )
        mock_supabase.table.assert_called()
        mock_query.insert.assert_not_called()
        mock_query.update.assert_not_called()

    def test_upsert_isochrones_update(self):
        """Test upsert_isochrones with existing records (update mode)"""
        mock_supabase = MagicMock()
        mock_query = MagicMock()
        mock_update = MagicMock()
        mock_execute = MagicMock()
        mock_supabase.table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute.return_value = self.mock_supabase_response
        mock_query.update.return_value = mock_update
        mock_update.eq.return_value = mock_execute
        mock_execute.execute.return_value = MagicMock(error=None, data=[{"id": 1}])
        upsert_isochrones(
            mock_supabase,
            "Test City 1",
            self.isochrone_result,
            dry_run=False,
            centers_df=self.centers_df,
        )
        mock_query.update.assert_called()

    def test_upsert_isochrones_insert(self):
        """Test upsert_isochrones with new records (insert mode)"""
        mock_supabase = MagicMock()
        mock_query = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        mock_supabase.table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        empty_response = MagicMock()
        empty_response.data = []
        mock_query.execute.return_value = empty_response
        mock_query.insert.return_value = mock_insert
        mock_insert.execute.return_value = mock_execute
        mock_execute.error = None
        mock_execute.data = [{"id": 123}]
        upsert_isochrones(
            mock_supabase,
            "Test City 1",
            self.isochrone_result,
            dry_run=False,
            centers_df=self.centers_df,
        )
        self.assertEqual(mock_query.insert.call_count, 2)

    def test_check_existing_isochrones(self):
        """Test checking for existing isochrones"""
        mock_supabase = MagicMock()
        mock_query = MagicMock()
        mock_supabase.table.return_value = mock_query
        mock_query.select.return_value = mock_query
        mock_query.limit.return_value = mock_query
        result_with_records = MagicMock()
        result_with_records.count = 5
        mock_query.execute.return_value = result_with_records
        self.assertTrue(check_existing_isochrones(mock_supabase))
        result_no_records = MagicMock()
        result_no_records.count = 0
        mock_query.execute.return_value = result_no_records
        self.assertFalse(check_existing_isochrones(mock_supabase))

    @patch("pathlib.Path.open", new_callable=mock_open)
    def test_save_geojson_file(self, mock_file):
        """Test saving GeoJSON to a file"""
        test_path = Path("/test/path/file.geojson")
        save_geojson_file(test_path, self.isochrone_result)
        mock_file.assert_called_once_with("w")
        handle = mock_file()
        handle.write.assert_called()

    @patch("pathlib.Path.open")
    def test_save_geojson_file_error(self, mock_open):
        """Test error handling when saving GeoJSON fails"""
        mock_open.side_effect = Exception("File error")
        with self.assertRaises(DataProcessingError):
            save_geojson_file(Path("/test/path/file.geojson"), self.isochrone_result)

    @patch("src.isochrone.json.dump")
    @patch("pathlib.Path.open", new_callable=mock_open)
    def test_save_geojson_json_error(self, mock_file, mock_dump):
        """Test handling JSON serialization errors"""
        mock_dump.side_effect = json.JSONDecodeError("JSON Error", "", 0)
        with self.assertRaises(GeoJSONError):
            save_geojson_file(Path("/test/path.geojson"), self.isochrone_result)

    @patch("src.isochrone.get_ors_client")
    @patch("src.isochrone.load_center_data")
    @patch("src.isochrone.generate_isochrone")
    @patch("src.isochrone.save_geojson_file")
    @patch("src.isochrone.Path")
    @patch("builtins.input", return_value="y")
    def test_main_local_mode(
        self,
        mock_input,
        mock_path,
        mock_save_geojson,
        mock_generate,
        mock_load_centers,
        mock_get_ors_client,
    ):
        """Test main function in local mode"""
        mock_path_instance = MagicMock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.mkdir.return_value = None
        mock_path_instance.glob.return_value = []
        mock_ors_client = MagicMock()
        mock_get_ors_client.return_value = mock_ors_client
        mock_load_centers.return_value = (
            self.centers_df,
            [[-122.4194, 37.7749], [-74.006, 40.7128]],
        )
        mock_generate.return_value = ("Test City 1", self.isochrone_result)
        with patch("sys.argv", ["isochrone.py", "--mode", "use-local"]):
            with patch(
                "argparse.ArgumentParser.parse_args",
                return_value=MagicMock(mode="use-local", dry_run=False),
            ):
                main()
        mock_load_centers.assert_called_once()
        mock_generate.assert_called()
        mock_save_geojson.assert_called()

    @patch("src.isochrone.get_ors_client")
    @patch("src.isochrone.get_supabase_client")
    @patch("src.isochrone.load_center_data")
    @patch("src.isochrone.generate_isochrone")
    @patch("src.isochrone.upsert_isochrones")
    @patch("src.isochrone.check_existing_isochrones")
    @patch("src.isochrone.Path")
    @patch("builtins.input", return_value="y")
    def test_main_db_mode(
        self,
        mock_input,
        mock_path,
        mock_check_existing,
        mock_upsert,
        mock_generate,
        mock_load_centers,
        mock_get_supabase,
        mock_get_ors_client,
    ):
        """Test main function in database mode"""
        mock_path_instance = MagicMock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.mkdir.return_value = None
        mock_path_instance.glob.return_value = []
        mock_ors_client = MagicMock()
        mock_get_ors_client.return_value = mock_ors_client
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase
        mock_check_existing.return_value = True
        mock_load_centers.return_value = (
            self.centers_df,
            [[-122.4194, 37.7749], [-74.006, 40.7128]],
        )
        mock_generate.return_value = ("Test City 1", self.isochrone_result)
        with patch("sys.argv", ["isochrone.py", "--mode", "use-db"]):
            with patch(
                "argparse.ArgumentParser.parse_args",
                return_value=MagicMock(mode="use-db", dry_run=False),
            ):
                main()
        mock_load_centers.assert_called_once()
        mock_check_existing.assert_called_once()
        mock_generate.assert_called()
        mock_upsert.assert_called()


if __name__ == "__main__":
    unittest.main()
