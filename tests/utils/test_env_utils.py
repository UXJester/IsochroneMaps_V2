import unittest
from unittest.mock import patch, MagicMock
import os

from src.utils.env_utils import load_env_variables
from src.utils.error_utils import ConfigMissingError


class TestEnvUtils(unittest.TestCase):
    @patch("src.utils.env_utils.load_dotenv")
    @patch("src.utils.env_utils.Path")
    def test_load_env_variables_success(self, mock_path, mock_load_dotenv):
        # Setup mock path and return values
        mock_project_root = MagicMock()
        mock_dotenv_path = MagicMock()
        mock_path.return_value.resolve.return_value.parent.parent.parent = (
            mock_project_root
        )
        mock_project_root.__truediv__.return_value = mock_dotenv_path

        # Configure load_dotenv to indicate success
        mock_load_dotenv.return_value = True

        # Call the function
        path, success = load_env_variables()

        # Assert
        self.assertEqual(path, mock_dotenv_path)
        self.assertTrue(success)
        mock_load_dotenv.assert_called_once_with(dotenv_path=mock_dotenv_path)

    @patch("src.utils.env_utils.load_dotenv")
    @patch("src.utils.env_utils.Path")
    @patch("src.utils.env_utils.logging")
    def test_load_env_variables_with_required_vars_all_present(
        self, mock_logging, mock_path, mock_load_dotenv
    ):
        # Setup
        mock_project_root = MagicMock()
        mock_dotenv_path = MagicMock()
        mock_path.return_value.resolve.return_value.parent.parent.parent = (
            mock_project_root
        )
        mock_project_root.__truediv__.return_value = mock_dotenv_path
        mock_load_dotenv.return_value = True

        # Setup env vars
        with patch.dict(
            os.environ, {"API_KEY": "test_key", "DATABASE_URL": "test_url"}
        ):
            # Call the function with required vars
            path, success = load_env_variables(
                required_vars=["API_KEY", "DATABASE_URL"]
            )

            # Assert
            self.assertEqual(path, mock_dotenv_path)
            self.assertTrue(success)
            mock_logging.warning.assert_not_called()

    @patch("src.utils.env_utils.load_dotenv")
    @patch("src.utils.env_utils.Path")
    @patch("src.utils.env_utils.logging")
    def test_load_env_variables_with_missing_required_vars(
        self, mock_logging, mock_path, mock_load_dotenv
    ):
        # Setup
        mock_project_root = MagicMock()
        mock_dotenv_path = MagicMock()
        mock_path.return_value.resolve.return_value.parent.parent.parent = (
            mock_project_root
        )
        mock_project_root.__truediv__.return_value = mock_dotenv_path
        mock_load_dotenv.return_value = True

        # Setup env vars (only one of the required vars is present)
        with patch.dict(os.environ, {"API_KEY": "test_key"}):
            # Call the function with required vars
            with self.assertRaises(ConfigMissingError):
                load_env_variables(required_vars=["API_KEY", "DATABASE_URL"])

            # Assert error was logged
            mock_logging.warning.assert_called_with(
                "Required environment variable missing: DATABASE_URL"
            )
            mock_logging.error.assert_called_once()

    @patch("src.utils.env_utils.load_dotenv")
    @patch("src.utils.env_utils.Path")
    @patch("src.utils.env_utils.logging")
    def test_load_env_variables_dotenv_failure(
        self, mock_logging, mock_path, mock_load_dotenv
    ):
        # Setup
        mock_project_root = MagicMock()
        mock_dotenv_path = MagicMock()
        mock_path.return_value.resolve.return_value.parent.parent.parent = (
            mock_project_root
        )
        mock_project_root.__truediv__.return_value = mock_dotenv_path

        # Configure load_dotenv to indicate failure
        mock_load_dotenv.return_value = False

        # Call the function
        path, success = load_env_variables()

        # Assert
        self.assertEqual(path, mock_dotenv_path)
        self.assertFalse(success)
        mock_load_dotenv.assert_called_once_with(dotenv_path=mock_dotenv_path)
        mock_logging.warning.assert_called_with(
            f".env file not found at {mock_dotenv_path}"
        )

    @patch("src.utils.env_utils.load_dotenv")
    @patch("src.utils.env_utils.Path")
    @patch("src.utils.env_utils.logging")
    def test_load_env_variables_with_empty_required_vars(
        self, mock_logging, mock_path, mock_load_dotenv
    ):
        # Setup
        mock_project_root = MagicMock()
        mock_dotenv_path = MagicMock()
        mock_path.return_value.resolve.return_value.parent.parent.parent = (
            mock_project_root
        )
        mock_project_root.__truediv__.return_value = mock_dotenv_path
        mock_load_dotenv.return_value = True

        # Call with empty required vars
        path, success = load_env_variables(required_vars=[])

        # Assert
        self.assertEqual(path, mock_dotenv_path)
        self.assertTrue(success)
        mock_logging.warning.assert_not_called()

    @patch("src.utils.env_utils.load_dotenv")
    @patch("src.utils.env_utils.Path")
    def test_load_env_variables_path_construction(self, mock_path, mock_load_dotenv):
        # Setup a more realistic path mock
        mock_file = MagicMock()
        mock_file_parent = MagicMock()
        mock_src_parent = MagicMock()
        mock_project_root = MagicMock()

        mock_path.return_value = mock_file
        mock_file.resolve.return_value = mock_file
        mock_file.parent = mock_file_parent
        mock_file_parent.parent = mock_src_parent
        mock_src_parent.parent = mock_project_root

        mock_dotenv_path = MagicMock()
        mock_project_root.__truediv__.return_value = mock_dotenv_path

        # Call the function
        path, success = load_env_variables()

        # Assert correct path construction - update to match actual implementation
        # This is the path to env_utils.py, not the test file
        mock_path.assert_called_once_with(
            __file__.replace("tests/utils/test_env_utils.py", "src/utils/env_utils.py")
        )
        # OR use a less brittle approach:
        self.assertTrue(mock_path.called)
        mock_project_root.__truediv__.assert_called_once_with(".env")
