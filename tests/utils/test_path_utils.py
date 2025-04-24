import os
import shutil
import tempfile
import unittest
from pathlib import Path

from src.utils.path_utils import ensure_dirs_exist


class TestPathUtils(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Clean up the temporary directory after tests
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_ensure_dirs_exist_single_directory(self):
        """Test that a single directory is created correctly."""
        test_path = os.path.join(self.test_dir, "test_dir")
        self.assertFalse(os.path.exists(test_path))

        # Call the function
        ensure_dirs_exist([test_path])

        # Check if directory was created
        self.assertTrue(os.path.exists(test_path))
        self.assertTrue(os.path.isdir(test_path))

    def test_ensure_dirs_exist_multiple_directories(self):
        """Test that multiple directories are created correctly."""
        test_paths = [
            os.path.join(self.test_dir, "dir1"),
            os.path.join(self.test_dir, "dir2"),
            os.path.join(self.test_dir, "dir3/subdir"),
        ]

        # Verify directories don't exist yet
        for path in test_paths:
            self.assertFalse(os.path.exists(path))

        # Call the function
        ensure_dirs_exist(test_paths)

        # Check if all directories were created
        for path in test_paths:
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.isdir(path))

    def test_ensure_dirs_exist_with_path_objects(self):
        """Test that the function works with Path objects."""
        test_paths = [
            Path(self.test_dir) / "path_dir1",
            Path(self.test_dir) / "path_dir2" / "subdir",
        ]

        # Verify directories don't exist yet
        for path in test_paths:
            self.assertFalse(path.exists())

        # Call the function
        ensure_dirs_exist(test_paths)

        # Check if all directories were created
        for path in test_paths:
            self.assertTrue(path.exists())
            self.assertTrue(path.is_dir())

    def test_ensure_dirs_exist_already_existing(self):
        """Test that the function handles already existing directories correctly."""
        # Create a directory first
        test_path = os.path.join(self.test_dir, "existing_dir")
        os.makedirs(test_path)

        # Place a file in the directory to check it's not removed
        test_file = os.path.join(test_path, "test_file.txt")
        with open(test_file, "w") as f:
            f.write("test content")

        # Call the function on the existing directory
        ensure_dirs_exist([test_path])

        # Directory should still exist
        self.assertTrue(os.path.exists(test_path))
        # File should still exist
        self.assertTrue(os.path.exists(test_file))

        # Read the file content to ensure it's unchanged
        with open(test_file, "r") as f:
            content = f.read()
        self.assertEqual(content, "test content")

    def test_ensure_dirs_exist_empty_list(self):
        """Test that the function handles an empty list correctly."""
        # Should not raise any exception
        ensure_dirs_exist([])

        # The test directory should still exist
        self.assertTrue(os.path.exists(self.test_dir))


if __name__ == "__main__":
    unittest.main()
