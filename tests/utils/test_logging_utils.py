import unittest
import logging
import tempfile
import io
from pathlib import Path
from unittest.mock import patch

from src.utils.logging_utils import (
    setup_logging,
    setup_structured_logging,
    LogContext,
    with_log_context,
    ContextAwareFormatter,
    clear_log_context,
)


class TestLoggingUtils(unittest.TestCase):
    def setUp(self):
        # Reset root logger before each test
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)
        # Reset logging configuration
        logging.basicConfig(handlers=[])
        # Clear any existing context
        clear_log_context()

    def tearDown(self):
        # Clean up any handlers that might have been created
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)
        # Clear any context
        clear_log_context()

    def test_setup_logging_basic(self):
        """Test basic logging setup without file handler."""
        setup_logging()

        # Check that the root logger has the expected level
        root_logger = logging.getLogger()
        self.assertEqual(root_logger.level, logging.INFO)

        # Check that there's at least one handler (the default console handler)
        self.assertGreaterEqual(len(root_logger.handlers), 1)

        # Check handler types and formatting
        console_handler = next(
            (h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)),
            None,
        )
        self.assertIsNotNone(console_handler, "No StreamHandler found")

        # Verify formatter is a ContextAwareFormatter
        self.assertIsInstance(console_handler.formatter, ContextAwareFormatter)

        if console_handler.formatter:
            self.assertTrue("%(asctime)s" in console_handler.formatter._fmt)
            self.assertTrue("%(levelname)s" in console_handler.formatter._fmt)
            self.assertTrue("%(message)s" in console_handler.formatter._fmt)

    def test_setup_logging_with_file(self):
        """Test logging setup with a file handler."""
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = "test_log.log"

            # Setup logging with the temporary directory
            setup_logging(log_file_name=log_file, logs_dir=temp_dir)

            # Get the root logger
            root_logger = logging.getLogger()

            # Check if a file handler was added
            file_handlers = [
                h for h in root_logger.handlers if isinstance(h, logging.FileHandler)
            ]
            self.assertGreaterEqual(len(file_handlers), 1, "No FileHandler was created")

            # Check if the file was created in the temp directory
            log_file_path = Path(temp_dir) / log_file
            self.assertTrue(
                log_file_path.exists(), f"Log file was not created at {log_file_path}"
            )

            # Write a test log message
            test_message = "This is a test log message"
            logging.info(test_message)

            # Check if the message was written to the file
            with open(log_file_path, "r") as f:
                log_content = f.read()
                self.assertIn(test_message, log_content)

    def test_setup_logging_default_dir(self):
        """Test logging with default directory creation."""
        # Create a temp dir to simulate project root
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_project_root = Path(temp_dir)

            # Mock the file resolution to use our temp directory
            original_path = Path.resolve

            try:
                # Mock the Path(__file__).resolve().parent.parent.parent path
                # Add self parameter to the mock function
                def mock_resolve(self):
                    class MockPath:
                        @property
                        def parent(self):
                            return self

                        def __truediv__(self, other):
                            return temp_project_root / other

                    return MockPath()

                # Replace Path.resolve with our mock
                Path.resolve = mock_resolve

                # This should create a logs directory in our temp dir
                log_file = "default_dir_test.log"
                setup_logging(log_file_name=log_file)

                # Check if logs directory was created
                logs_dir = temp_project_root / "logs"
                self.assertTrue(
                    logs_dir.exists(), "Default logs directory was not created"
                )

                # Check if log file was created inside
                expected_log_path = logs_dir / log_file
                self.assertTrue(
                    expected_log_path.is_file(),
                    "Log file was not created in default directory",
                )

            finally:
                # Restore original method
                Path.resolve = original_path

    def test_multiple_setup_calls(self):
        """Test that multiple setup_logging calls work as expected."""
        # First call with no file
        setup_logging()
        initial_handler_count = len(logging.getLogger().handlers)

        # Second call with a file
        with tempfile.TemporaryDirectory() as temp_dir:
            setup_logging(log_file_name="second_call.log", logs_dir=temp_dir)

            # Check that a new handler was added
            new_handler_count = len(logging.getLogger().handlers)
            self.assertEqual(
                new_handler_count,
                initial_handler_count + 1,
                "Second call should add exactly one handler",
            )

            # Check file was created
            log_path = Path(temp_dir) / "second_call.log"
            self.assertTrue(
                log_path.exists(), "Log file was not created on second call"
            )

    @patch("src.utils.logging_utils.setup_logging")
    def test_setup_structured_logging(self, mock_setup_logging):
        """Test that structured logging setup works correctly."""
        # Call the function
        setup_structured_logging(
            log_file="test.log",
            logs_dir="/tmp",
            level=logging.DEBUG,
            request_id="test-id",
        )

        # Verify setup_logging was called with expected parameters
        mock_setup_logging.assert_called_once_with(
            log_file_name="test.log",
            logs_dir="/tmp",
            level=logging.DEBUG,
            format_string="%(asctime)s - %(levelname)s - %(name)s - %(request_id)s - %(message)s",
            add_request_id=True,
            request_id="test-id",
        )

    def test_log_context_manager_basic(self):
        """Test that LogContext properly sets context values."""
        # Before context, should be empty
        clear_log_context()

        # Verify initial state
        self.assertFalse(hasattr(logging, "context"))

        with LogContext(operation="test_op", user_id="123"):
            # Inside context, values should be set
            self.assertTrue(hasattr(logging, "context"))
            self.assertEqual(logging.context.get("operation"), "test_op")
            self.assertEqual(logging.context.get("user_id"), "123")

        # After context, values should be back to previous state (empty in this case)
        # In the implementation, LogContext.__exit__ restores self.old_context (which is {} initially)
        # So after the context exits, logging.context should be empty ({}) but still exist
        self.assertTrue(hasattr(logging, "context"))
        self.assertEqual(logging.context, {})

    def test_nested_log_context(self):
        """Test that nested LogContexts properly merge."""
        # Ensure clean state
        clear_log_context()
        # Initial setup - the LogContext in __init__ creates an empty dict
        logging.context = {}

        with LogContext(service="auth"):
            self.assertEqual(logging.context.get("service"), "auth")

            with LogContext(operation="login"):
                self.assertEqual(logging.context.get("service"), "auth")
                self.assertEqual(logging.context.get("operation"), "login")

                with LogContext(user_id="123"):
                    self.assertEqual(logging.context.get("service"), "auth")
                    self.assertEqual(logging.context.get("operation"), "login")
                    self.assertEqual(logging.context.get("user_id"), "123")

                # After inner context
                self.assertEqual(logging.context.get("service"), "auth")
                self.assertEqual(logging.context.get("operation"), "login")
                self.assertNotIn("user_id", logging.context)

            # After middle context
            self.assertEqual(logging.context.get("service"), "auth")
            self.assertNotIn("operation", logging.context)

        # After outer context - should be back to empty but still exist
        self.assertTrue(hasattr(logging, "context"))
        self.assertEqual(logging.context, {})

    def test_with_log_context_decorator(self):
        """Test that the with_log_context decorator sets context values."""
        # Ensure clean state
        clear_log_context()
        # Initial setup - the decorator ultimately creates an empty dict through LogContext
        logging.context = {}

        @with_log_context(module="test_module", operation="test_operation")
        def test_function(arg1, arg2=None):
            # Access the parameters to avoid unaccessed parameter warnings
            _ = arg1, arg2
            return logging.context

        # Call the function and check context
        context = test_function("value1", arg2="value2")
        self.assertEqual(context.get("module"), "test_module")
        self.assertEqual(context.get("operation"), "test_operation")

        # After function call, context should be back to empty (the old context)
        self.assertTrue(hasattr(logging, "context"))
        self.assertEqual(logging.context, {})

    @patch("logging.Logger.info")
    def test_actual_logging_with_context(self, mock_log_info):
        """Test integration of context with actual logging calls."""
        # Ensure clean state
        if hasattr(logging, "context"):
            delattr(logging, "context")

        logger = logging.getLogger("test")

        with LogContext(request_id="abc123"):
            logger.info("Processing request")

        # Check that context was passed to the log call
        mock_log_info.assert_called_once()

    def test_structured_log_output_format(self):
        """Test that log messages are properly formatted with context."""
        # Create a simple logger for testing
        test_logger = logging.getLogger("test.formatter")
        test_logger.setLevel(logging.INFO)

        # Create string IO to capture the logs
        string_io = io.StringIO()
        handler = logging.StreamHandler(string_io)

        # Add our context aware formatter with explicit attributes
        formatter = ContextAwareFormatter(
            "%(levelname)s - %(message)s - %(operation)s - %(user_id)s"
        )
        handler.setFormatter(formatter)
        test_logger.addHandler(handler)

        # Set context values
        logging.context = {"operation": "test_op", "user_id": "user123"}

        # Log a message
        test_logger.info("Test message")

        # Get the log output
        output = string_io.getvalue()

        # Check that the output contains our context values
        self.assertIn("test_op", output)
        self.assertIn("user123", output)

        # Clean up the context
        if hasattr(logging, "context"):
            delattr(logging, "context")

    def test_log_context_with_non_string_values(self):
        """Test that LogContext handles non-string values."""
        # Ensure clean state
        if hasattr(logging, "context"):
            delattr(logging, "context")

        complex_value = {"nested": {"data": [1, 2, 3]}}

        with LogContext(complex_key=complex_value, number=42, boolean=True):
            self.assertTrue(hasattr(logging, "context"))
            self.assertEqual(logging.context.get("complex_key"), complex_value)
            self.assertEqual(logging.context.get("number"), 42)
            self.assertEqual(logging.context.get("boolean"), True)


if __name__ == "__main__":
    unittest.main()
