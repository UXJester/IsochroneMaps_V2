import unittest
from unittest.mock import patch

from src.utils.error_utils import (
    ExceptionContext,
    AppError,
    DataError,
    ConfigError,
    APIError,
    handle_exception,
    convert_exception,
)


class TestErrorUtils(unittest.TestCase):
    def test_exception_context_manager(self):
        """Test that ExceptionContext properly wraps exceptions with context information."""
        with self.assertRaises(AppError) as cm:
            with ExceptionContext("Test operation"):
                raise ValueError("Original error")

        error_msg = str(cm.exception)
        self.assertIn("Test operation", error_msg)
        self.assertIn("Original error", error_msg)

    def test_exception_context_with_custom_error(self):
        """Test ExceptionContext with custom error class."""
        with self.assertRaises(DataError) as cm:
            with ExceptionContext("Test operation", error_cls=DataError):
                raise ValueError("Original error")

        error_msg = str(cm.exception)
        self.assertIn("Test operation", error_msg)
        self.assertIn("Original error", error_msg)

    def test_exception_context_with_app_error(self):
        """Test that ExceptionContext passes through AppError exceptions."""
        with self.assertRaises(APIError) as cm:
            with ExceptionContext("Test operation"):
                raise APIError("API error")

        self.assertIsInstance(cm.exception, APIError)
        self.assertEqual(str(cm.exception), "API error")

    def test_api_error(self):
        """Test that APIError works as expected."""
        error = APIError("API request failed")
        self.assertIsInstance(error, AppError)
        self.assertEqual(str(error), "API request failed")

    def test_data_error(self):
        """Test that DataError works as expected."""
        error = DataError("Data validation failed")
        self.assertIsInstance(error, AppError)
        self.assertEqual(str(error), "Data validation failed")

    def test_config_error(self):
        """Test that ConfigError works as expected."""
        error = ConfigError("Missing configuration")
        self.assertIsInstance(error, AppError)
        self.assertEqual(str(error), "Missing configuration")

    def test_convert_exception(self):
        """Test that convert_exception works as expected."""
        original = ValueError("Original error")
        converted = convert_exception(original, DataError)

        self.assertIsInstance(converted, DataError)
        self.assertEqual(str(converted), "Original error")

        # Test with custom message
        converted_with_msg = convert_exception(original, ConfigError, "Custom message")
        self.assertIsInstance(converted_with_msg, ConfigError)
        self.assertEqual(str(converted_with_msg), "Custom message")

    @patch("src.utils.error_utils.logging")
    def test_handle_exception_decorator(self, mock_logging):
        """Test the handle_exception decorator."""

        @handle_exception
        def failing_function():
            raise ValueError("Original error")

        with self.assertRaises(AppError) as cm:
            failing_function()

        error_msg = str(cm.exception)
        self.assertIn("Unexpected error", error_msg)
        self.assertIn("Original error", error_msg)

        # Check that the error was logged
        mock_logging.error.assert_called()

    @patch("src.utils.error_utils.logging")
    def test_handle_exception_with_mapping(self, mock_logging):
        """Test that handle_exception works with custom mapping."""

        mapping = {ValueError: DataError}

        @handle_exception(custom_mapping=mapping)
        def failing_function():
            raise ValueError("Mapped error")

        with self.assertRaises(DataError) as cm:
            failing_function()

        error_msg = str(cm.exception)
        self.assertEqual(error_msg, "Mapped error")

    def test_exception_context_no_exception(self):
        """Test that ExceptionContext works when no exception is raised."""
        try:
            with ExceptionContext("Test operation"):
                pass  # No exception
            success = True
        except Exception:
            success = False

        self.assertTrue(success)


if __name__ == "__main__":
    unittest.main()
