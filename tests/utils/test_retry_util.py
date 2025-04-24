import unittest
from unittest.mock import Mock, patch, call

from src.utils.retry_util import retry
from src.utils.error_utils import APIError


class TestRetryUtil(unittest.TestCase):
    def test_successful_execution_first_try(self):
        """Test that a function that succeeds on first try returns the expected result."""
        mock_func = Mock(return_value="success")

        result = retry(mock_func, retries=3, delay=0.1)

        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 1)

    def test_eventual_success(self):
        """Test that a function that fails initially but eventually succeeds returns the expected result."""
        # Mock that fails twice then succeeds
        mock_func = Mock(
            side_effect=[ValueError("Failed"), ValueError("Failed"), "success"]
        )

        result = retry(mock_func, retries=3, delay=0.1)

        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 3)

    def test_all_attempts_fail(self):
        """Test that a function that always fails raises the specified error type."""
        mock_func = Mock(side_effect=ValueError("Failed"))

        with self.assertRaises(APIError) as context:
            retry(mock_func, retries=3, delay=0.1)

        self.assertTrue("failed after 3 attempts" in str(context.exception))
        self.assertEqual(mock_func.call_count, 3)

    @patch("time.sleep")  # Mock sleep to speed up tests
    def test_delay_between_retries(self, mock_sleep):
        """Test that there is a delay between retry attempts with progressive backoff."""
        mock_func = Mock(
            side_effect=[ValueError("Failed"), ValueError("Failed"), "success"]
        )

        retry(mock_func, retries=3, delay=2)

        # Verify sleep was called with progressive backoff
        mock_sleep.assert_has_calls([call(2), call(4)])
        self.assertEqual(mock_sleep.call_count, 2)

    def test_custom_error_handler(self):
        """Test that custom error handler is called on failures."""
        error_handler = Mock()
        mock_func = Mock(side_effect=[ValueError("Failed"), "success"])

        result = retry(mock_func, retries=2, delay=0.1, error_handler=error_handler)

        self.assertEqual(result, "success")
        self.assertEqual(error_handler.call_count, 1)
        # Verify error_handler was called with the exception and attempt index
        args, _ = error_handler.call_args
        self.assertIsInstance(args[0], ValueError)
        self.assertEqual(args[1], 0)  # First attempt (0-indexed)

    def test_different_exceptions(self):
        """Test handling of different types of exceptions."""
        mock_func = Mock(
            side_effect=[ValueError("Value error"), KeyError("Key error"), "success"]
        )

        result = retry(mock_func, retries=3, delay=0.1)

        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 3)

    @patch("src.utils.retry_util.logging")
    def test_logging_behavior(self, mock_logging):
        """Test that attempts are properly logged."""
        mock_func = Mock(side_effect=[ValueError("Failed"), "success"])

        result = retry(mock_func, retries=2, delay=0.1)

        self.assertEqual(result, "success")
        # Verify various log levels were called
        mock_logging.info.assert_called()
        mock_logging.warning.assert_called_once()
        mock_logging.error.assert_not_called()

    @patch("src.utils.retry_util.logging")
    def test_logging_all_attempts_failed(self, mock_logging):
        """Test that all failed attempts are properly logged."""
        mock_func = Mock(side_effect=ValueError("Failed"))

        with self.assertRaises(APIError):
            retry(mock_func, retries=2, delay=0.1)

        mock_logging.warning.assert_called()
        mock_logging.error.assert_called()

    def test_error_handler_exception(self):
        """Test that exceptions in the error handler are caught and logged."""
        # Create an error handler that raises an exception
        error_handler = Mock(side_effect=Exception("Error handler failed"))
        mock_func = Mock(side_effect=[ValueError("Failed"), "success"])

        with patch("src.utils.retry_util.logging") as mock_logging:
            result = retry(mock_func, retries=2, delay=0.1, error_handler=error_handler)

        self.assertEqual(result, "success")
        mock_logging.error.assert_called()

    def test_custom_error_type(self):
        """Test that a custom error type can be specified."""

        class CustomError(Exception):
            pass

        mock_func = Mock(side_effect=ValueError("Failed"))

        with self.assertRaises(CustomError):
            retry(mock_func, retries=2, delay=0.1, error_type=CustomError)


if __name__ == "__main__":
    unittest.main()
