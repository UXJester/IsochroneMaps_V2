import unittest
from unittest.mock import patch, MagicMock

from src.utils.client_utils import get_ors_client, get_supabase_client
from src.utils.error_utils import ConfigError, APIConnectionError


class TestClientUtils(unittest.TestCase):
    @patch("src.utils.client_utils.os.getenv")
    @patch("src.utils.client_utils.openrouteservice.Client")
    def test_get_ors_client_success(self, mock_ors_client, mock_getenv):
        # Setup mock
        mock_getenv.return_value = "fake_api_key"
        mock_client = MagicMock()
        mock_ors_client.return_value = mock_client

        # Execute
        result = get_ors_client()

        # Assert
        mock_getenv.assert_called_once_with("ORS_API_KEY")
        mock_ors_client.assert_called_once_with(key="fake_api_key")
        self.assertEqual(result, mock_client)

    @patch("src.utils.client_utils.os.getenv")
    def test_get_ors_client_missing_api_key(self, mock_getenv):
        # Setup mock
        mock_getenv.return_value = None

        # Execute & Assert
        with self.assertRaises(ConfigError) as context:
            get_ors_client()

        self.assertIn("ORS API key not found", str(context.exception))

    @patch("src.utils.client_utils.os.getenv")
    @patch("src.utils.client_utils.openrouteservice.Client")
    def test_get_ors_client_exception(self, mock_ors_client, mock_getenv):
        # Setup mock
        mock_getenv.return_value = "fake_api_key"
        mock_ors_client.side_effect = Exception("Connection error")

        # Execute & Assert
        with self.assertRaises(APIConnectionError) as context:
            get_ors_client()

        self.assertIn("Connection error", str(context.exception))

    @patch("src.utils.client_utils.os.getenv")
    @patch("src.utils.client_utils.create_client")
    def test_get_supabase_client_success(self, mock_create_client, mock_getenv):
        # Setup mock
        mock_getenv.side_effect = lambda key: {
            "SUPABASE_URL": "https://fake-url.supabase.co",
            "SUPABASE_KEY": "fake_key",
        }.get(key)

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Execute
        result = get_supabase_client()

        # Assert
        mock_create_client.assert_called_once_with(
            "https://fake-url.supabase.co", "fake_key"
        )
        self.assertEqual(result, mock_client)

    @patch("src.utils.client_utils.os.getenv")
    def test_get_supabase_client_missing_url(self, mock_getenv):
        # Setup mock
        mock_getenv.side_effect = lambda key: {
            "SUPABASE_URL": None,
            "SUPABASE_KEY": "fake_key",
        }.get(key)

        # Execute & Assert
        with self.assertRaises(ConfigError) as context:
            get_supabase_client()

        self.assertIn("Supabase URL not found", str(context.exception))

    @patch("src.utils.client_utils.os.getenv")
    def test_get_supabase_client_missing_key(self, mock_getenv):
        # Setup mock
        mock_getenv.side_effect = lambda key: {
            "SUPABASE_URL": "https://fake-url.supabase.co",
            "SUPABASE_KEY": None,
        }.get(key)

        # Execute & Assert
        with self.assertRaises(ConfigError) as context:
            get_supabase_client()

        self.assertIn("Supabase key not found", str(context.exception))

    @patch("src.utils.client_utils.os.getenv")
    @patch("src.utils.client_utils.create_client")
    def test_get_supabase_client_exception(self, mock_create_client, mock_getenv):
        # Setup mock
        mock_getenv.side_effect = lambda key: {
            "SUPABASE_URL": "https://fake-url.supabase.co",
            "SUPABASE_KEY": "fake_key",
        }.get(key)

        mock_create_client.side_effect = Exception("Connection error")

        # Execute & Assert
        with self.assertRaises(APIConnectionError) as context:
            get_supabase_client()

        self.assertIn("Connection error", str(context.exception))


if __name__ == "__main__":
    unittest.main()
