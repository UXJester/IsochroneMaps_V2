import unittest
from unittest.mock import patch, MagicMock, call
import pandas as pd
from src.geocode import (
    initialize_geolocator,
    geocode,
    geocode_dataset,
    load_csv_data,
    process_csv_source,
    process_db_source,
    process_csv_mode,
    process_db_mode,
)
from src.utils.error_utils import (
    AppError,
)


class TestGeocode(unittest.TestCase):

    @patch("src.geocode.Nominatim")
    @patch("src.geocode.ssl.create_default_context")
    def test_initialize_geolocator(self, mock_create_context, mock_nominatim):
        """Test that the geolocator is properly initialized with SSL context and appropriate settings."""
        mock_ssl_context = MagicMock()
        mock_create_context.return_value = mock_ssl_context
        mock_geolocator = MagicMock()
        mock_nominatim.return_value = mock_geolocator

        geolocator = initialize_geolocator()

        self.assertEqual(geolocator, mock_geolocator)
        mock_nominatim.assert_called_once_with(
            user_agent="geo_mapper", ssl_context=mock_ssl_context, timeout=10
        )
        mock_create_context.assert_called_once()

    @patch("src.geocode.initialize_geolocator")
    def test_geocode_valid_address(self, mock_initialize_geolocator):
        """Test geocoding with a valid address returns correct latitude and longitude."""
        mock_geolocator = MagicMock()
        mock_initialize_geolocator.return_value = mock_geolocator
        mock_location = MagicMock(
            latitude=38.8977, longitude=-77.0365, raw={"place_id": 12345}
        )
        mock_geolocator.geocode.return_value = mock_location

        lat, lon, error = geocode(
            "1600 Pennsylvania Ave",
            "Washington",
            "DC",
            "20500",
            geolocator=mock_geolocator,
        )

        self.assertEqual(lat, 38.8977)
        self.assertEqual(lon, -77.0365)
        self.assertEqual(error, "")
        mock_geolocator.geocode.assert_called_once_with(
            "1600 Pennsylvania Ave, Washington, DC, 20500"
        )

    @patch("src.geocode.initialize_geolocator")
    def test_geocode_with_location_name(self, mock_initialize_geolocator):
        """Test that location_name parameter is used when address geocoding fails."""
        mock_geolocator = MagicMock()
        mock_initialize_geolocator.return_value = mock_geolocator
        mock_location = MagicMock(
            latitude=37.7749, longitude=-122.4194, raw={"place_id": 12345}
        )
        # First call returns None (address fails), second call succeeds (location name works)
        mock_geolocator.geocode.side_effect = [None, mock_location]

        lat, lon, error = geocode(
            "",
            "San Francisco",
            "CA",
            "94103",
            geolocator=mock_geolocator,
            location_name="Golden Gate Park",
        )

        self.assertEqual(lat, 37.7749)
        self.assertEqual(lon, -122.4194)
        self.assertEqual(error, "")
        # Verify both calls are made - first with empty address, then with location name
        self.assertEqual(mock_geolocator.geocode.call_count, 2)
        mock_geolocator.geocode.assert_any_call("Golden Gate Park")
        mock_geolocator.geocode.assert_any_call("San Francisco, CA, 94103")

    @patch("src.geocode.initialize_geolocator")
    def test_geocode_fallback_to_city_state_zip(self, mock_initialize_geolocator):
        """Test fallback to city/state/zip when specific address geocoding fails."""
        mock_geolocator = MagicMock()
        mock_initialize_geolocator.return_value = mock_geolocator
        mock_location = MagicMock(
            latitude=38.9072, longitude=-77.0369, raw={"place_id": 12345}
        )
        # Address fails, location name not provided, city/state/zip succeeds
        mock_geolocator.geocode.side_effect = [None, mock_location]

        lat, lon, error = geocode(
            "Invalid Address", "Washington", "DC", "20001", geolocator=mock_geolocator
        )

        self.assertEqual(lat, 38.9072)
        self.assertEqual(lon, -77.0369)
        # Should have error message since we had to fall back to city center
        self.assertEqual(error, "Geocoded to city center - needs manual review")
        self.assertEqual(mock_geolocator.geocode.call_count, 2)
        mock_geolocator.geocode.assert_has_calls(
            [
                call("Invalid Address, Washington, DC, 20001"),
                call("Washington, DC, 20001"),
            ]
        )

    @patch("src.geocode.initialize_geolocator")
    def test_geocode_invalid_address(self, mock_initialize_geolocator):
        """Test behavior when all geocoding attempts fail."""
        mock_geolocator = MagicMock()
        mock_initialize_geolocator.return_value = mock_geolocator
        # All geocoding attempts fail
        mock_geolocator.geocode.side_effect = [None, None]

        lat, lon, error = geocode(
            "Invalid Address", "Unknown", "XX", "", geolocator=mock_geolocator
        )

        self.assertIsNone(lat)
        self.assertIsNone(lon)
        self.assertEqual(error, "Location not found")
        self.assertEqual(mock_geolocator.geocode.call_count, 2)
        mock_geolocator.geocode.assert_has_calls(
            [call("Invalid Address, Unknown, XX"), call("Unknown, XX")]
        )

    @patch("src.geocode.initialize_geolocator")
    def test_geocode_exception_handling(self, mock_initialize_geolocator):
        """Test that exceptions from the geocoding service are properly handled and reported."""
        mock_geolocator = MagicMock()
        mock_initialize_geolocator.return_value = mock_geolocator
        # Both geocoding attempts raise exceptions
        mock_geolocator.geocode.side_effect = [
            Exception("API Error"),
            Exception("API Error"),
        ]

        lat, lon, error = geocode(
            "Address", "City", "State", "12345", geolocator=mock_geolocator
        )

        self.assertIsNone(lat)
        self.assertIsNone(lon)
        # Verify the error message includes context from the geocode function
        self.assertEqual(error, "Error in Geocoding city,state,zip: API Error")
        self.assertEqual(mock_geolocator.geocode.call_count, 2)
        mock_geolocator.geocode.assert_any_call("Address, City, State, 12345")
        mock_geolocator.geocode.assert_any_call("City, State, 12345")

    @patch("src.geocode.initialize_geolocator")
    def test_geocode_with_none_values(self, mock_initialize_geolocator):
        """Test geocoding handles None values properly by converting them to empty strings."""
        mock_geolocator = MagicMock()
        mock_initialize_geolocator.return_value = mock_geolocator
        mock_location = MagicMock(
            latitude=37.7749, longitude=-122.4194, raw={"place_id": 12345}
        )
        mock_geolocator.geocode.return_value = mock_location

        # Test handling None values
        lat, lon, error = geocode(
            None, "San Francisco", "CA", "94103", geolocator=mock_geolocator
        )

        # Check that the function properly handles None by converting to empty string
        mock_geolocator.geocode.assert_called_once_with("San Francisco, CA, 94103")
        self.assertEqual(lat, 37.7749)
        self.assertEqual(lon, -122.4194)
        self.assertEqual(error, "")

    @patch("src.geocode.initialize_geolocator")
    def test_geocode_dataset(self, mock_initialize_geolocator):
        """Test dataset geocoding with different scenarios: valid address, location name fallback, and failure."""
        mock_geolocator = MagicMock()
        mock_initialize_geolocator.return_value = mock_geolocator

        # Configure different responses for different address combinations
        def geocode_side_effect(*args, **kwargs):
            address = args[0]
            if "1600 Pennsylvania" in address:
                return MagicMock(latitude=38.8977, longitude=-77.0365, raw={})
            elif "Golden Gate Park" in address:
                return MagicMock(latitude=37.7749, longitude=-122.4194, raw={})
            elif "San Francisco" in address:
                return MagicMock(latitude=37.7749, longitude=-122.4194, raw={})
            else:
                return None

        mock_geolocator.geocode.side_effect = geocode_side_effect

        # Create test dataset with three rows:
        # 1. Valid address
        # 2. Invalid address that will geocode using location_name
        # 3. Invalid address that will fail completely
        data = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "address": [
                    "1600 Pennsylvania Ave",
                    "Invalid Address",
                    "Unknown Location",
                ],
                "city": ["Washington", "San Francisco", ""],
                "state": ["DC", "CA", ""],
                "zip_code": ["20500", "94103", ""],
                "name": [None, "Golden Gate Park", None],
                "latitude": [None, None, None],
                "longitude": [None, None, None],
                "error": [None, None, None],
            }
        )

        columns_config = {
            "id": "id",
            "address": "address",
            "city": "city",
            "state": "state",
            "zip_code": "zip_code",
            "name": "name",
            "latitude": "latitude",
            "longitude": "longitude",
            "error": "error",
        }

        processed_data, success_count, error_count = geocode_dataset(
            data, columns_config, geolocator=mock_geolocator
        )

        # Verify statistics
        self.assertEqual(success_count, 2)
        self.assertEqual(error_count, 1)

        # Check first row - valid address
        self.assertEqual(processed_data.loc[0, "latitude"], 38.8977)
        self.assertEqual(processed_data.loc[0, "longitude"], -77.0365)
        self.assertIsNone(processed_data.loc[0, "error"])
        self.assertTrue(processed_data.loc[0, "_needs_update"])

        # Check second row - geocoded via location_name
        self.assertEqual(processed_data.loc[1, "latitude"], 37.7749)
        self.assertEqual(processed_data.loc[1, "longitude"], -122.4194)
        self.assertIsNone(processed_data.loc[1, "error"])
        self.assertTrue(processed_data.loc[1, "_needs_update"])

        # Check third row - failed to geocode
        self.assertIsNone(processed_data.loc[2, "latitude"])
        self.assertIsNone(processed_data.loc[2, "longitude"])
        self.assertEqual(processed_data.loc[2, "error"], "Location not found")
        self.assertTrue(processed_data.loc[2, "_needs_update"])

        self.assertEqual(mock_geolocator.geocode.call_count, 3)

    @patch("pandas.read_csv")
    @patch("os.path.exists")
    def test_load_csv_data(self, mock_path_exists, mock_read_csv):
        """Test that CSV data is correctly loaded when the file exists."""
        mock_path_exists.return_value = True
        mock_df = pd.DataFrame({"column1": [1, 2, 3]})
        mock_read_csv.return_value = mock_df

        df = load_csv_data("test.csv")

        self.assertTrue(df.equals(mock_df))
        mock_read_csv.assert_called_once_with("test.csv", dtype=None)

    @patch("os.path.exists")
    def test_load_csv_data_file_not_found(self, mock_path_exists):
        """Test that an appropriate error is raised when the CSV file doesn't exist."""
        mock_path_exists.return_value = False

        # The function's error is wrapped in AppError by the error handler decorator
        with self.assertRaises(AppError):
            load_csv_data("nonexistent.csv")

    @patch("src.geocode.load_csv_data")
    @patch("src.geocode.geocode_dataset")
    @patch("pandas.DataFrame.to_csv")
    def test_process_csv_source(
        self, mock_to_csv, mock_geocode_dataset, mock_load_csv_data
    ):
        """Test that CSV source processing correctly handles data loading, geocoding, and saving results."""
        mock_df = pd.DataFrame({"column1": [1, 2, 3]})
        processed_df = mock_df.copy()
        processed_df["_needs_update"] = True

        mock_load_csv_data.return_value = mock_df
        mock_geocode_dataset.return_value = (processed_df, 2, 1)

        process_csv_source(
            "input.csv", "output.csv", {"latitude": "lat", "longitude": "lon"}
        )

        mock_load_csv_data.assert_called_once_with("input.csv", dtype={"zip_code": str})
        mock_geocode_dataset.assert_called_once()
        mock_to_csv.assert_called_once_with("output.csv", index=False)

    @patch("src.geocode.load_csv_data")
    @patch("src.geocode.geocode_dataset")
    @patch("pandas.DataFrame.to_csv")
    def test_process_csv_source_no_changes(
        self, mock_to_csv, mock_geocode_dataset, mock_load_csv_data
    ):
        """Test that when no geocoding changes are needed, the output file isn't written."""
        mock_df = pd.DataFrame({"column1": [1, 2, 3]})
        mock_load_csv_data.return_value = mock_df
        mock_geocode_dataset.return_value = (mock_df, 0, 0)

        process_csv_source(
            "input.csv", "output.csv", {"latitude": "lat", "longitude": "lon"}
        )

        mock_load_csv_data.assert_called_once()
        mock_geocode_dataset.assert_called_once()
        # Verify to_csv is not called when no changes needed
        mock_to_csv.assert_not_called()

    @patch("src.geocode.load_data")
    @patch("src.geocode.initialize_geolocator")
    @patch("src.geocode.geocode_dataset")
    def test_process_db_source(
        self, mock_geocode_dataset, mock_initialize_geolocator, mock_load_data
    ):
        """Test database geocoding with row updates for records that need changes."""
        # Setup mock data and objects
        mock_supabase_client = MagicMock()
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_eq = MagicMock()

        # Configure the mock chain
        mock_supabase_client.table.return_value = mock_table
        mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq

        # Create test data with one record needing update
        test_df = pd.DataFrame(
            {
                "id": [1, 2],
                "address": ["123 Main St", "456 Oak Ave"],
                "city": ["Springfield", "Rivertown"],
                "state": ["IL", "CA"],
                "zip_code": ["62701", "90210"],
                "latitude": [None, 34.5],
                "longitude": [None, -118.2],
                "error": [None, None],
            }
        )

        # Setup geocode_dataset to return modified data
        processed_df = test_df.copy()
        processed_df["latitude"] = [37.5, 34.5]
        processed_df["longitude"] = [-122.1, -118.2]
        processed_df["_needs_update"] = [True, False]
        mock_geocode_dataset.return_value = (processed_df, 1, 0)

        # Mock loading data from database
        mock_load_data.return_value = test_df

        # Setup test config
        table_config = {
            "table_name": "locations",
            "columns": {
                "id": "id",
                "address": "address",
                "city": "city",
                "state": "state",
                "zip_code": "zip_code",
                "latitude": "latitude",
                "longitude": "longitude",
                "error": "error",
            },
        }

        # Run the function
        process_db_source(table_config, mock_supabase_client)

        # Verify interactions
        mock_load_data.assert_called_once_with(mock_supabase_client, "locations")
        mock_geocode_dataset.assert_called_once()

        # Verify database update was called with correct parameters for only the first row
        mock_supabase_client.table.assert_called_with("locations")
        mock_table.update.assert_called_with(
            {"latitude": 37.5, "longitude": -122.1, "error": None}
        )
        mock_update.eq.assert_called_with("id", 1)
        mock_eq.execute.assert_called_once()

    @patch("src.geocode.process_db_source")
    @patch("src.geocode.get_supabase_client")
    def test_process_db_mode(self, mock_get_supabase_client, mock_process_db_source):
        """Test that database mode only processes tables configured for geocoding."""
        # Setup mock client
        mock_client = MagicMock()
        mock_get_supabase_client.return_value = mock_client

        # Mock TABLES global
        tables_mock = {
            "table1": {
                "needs_geocoding": True,
                "table_name": "locations",
                "columns": {"id": "id"},
            },
            "table2": {"needs_geocoding": False, "table_name": "other_table"},
        }

        with patch("src.geocode.TABLES", tables_mock):
            process_db_mode()

        # Verify process_db_source only called for table with needs_geocoding=True
        mock_process_db_source.assert_called_once()
        mock_process_db_source.assert_called_with(tables_mock["table1"], mock_client)

    @patch("os.path.exists")
    @patch("src.geocode.process_csv_source")
    def test_process_csv_mode(self, mock_process_csv_source, mock_path_exists):
        """Test that CSV mode correctly handles file selection and only processes tables configured for geocoding."""
        # Always return True for os.path.exists to use geocoded file as input
        mock_path_exists.return_value = True

        # Mock TABLES and LOCATIONS globals
        tables_mock = {
            "table1": {
                "needs_geocoding": True,
                "table_name": "locations",
                "columns": {"id": "id"},
            },
            "table2": {"needs_geocoding": False, "table_name": "other_table"},
        }

        locations_dir = "/test/locations"

        with patch("src.geocode.TABLES", tables_mock), patch(
            "src.geocode.LOCATIONS", locations_dir
        ):
            process_csv_mode()

        # Verify process_csv_source only called for table with needs_geocoding=True
        # and with the correct file paths
        mock_process_csv_source.assert_called_once()
        mock_process_csv_source.assert_called_with(
            f"{locations_dir}/geocoded_locations.csv",
            f"{locations_dir}/geocoded_locations.csv",
            tables_mock["table1"]["columns"],
        )


if __name__ == "__main__":
    unittest.main()
