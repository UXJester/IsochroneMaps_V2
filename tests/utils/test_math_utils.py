import unittest
from src.utils.math_utils import calculate_geographic_midpoint
from src.utils.error_utils import DataValidationError


class TestMathUtils(unittest.TestCase):
    def test_calculate_geographic_midpoint_basic(self):
        """Test basic midpoint calculation with two points."""
        coords = [(0, 0), (0, 180)]
        expected = [0, 90]
        result = calculate_geographic_midpoint(coords)
        self.assertAlmostEqual(result[0], expected[0], places=5)
        self.assertAlmostEqual(result[1], expected[1], places=5)

    def test_calculate_geographic_midpoint_same_point(self):
        """Test midpoint calculation with identical points."""
        coords = [(45.0, -75.0), (45.0, -75.0), (45.0, -75.0)]
        expected = [45.0, -75.0]
        result = calculate_geographic_midpoint(coords)
        self.assertAlmostEqual(result[0], expected[0], places=5)
        self.assertAlmostEqual(result[1], expected[1], places=5)

    def test_calculate_geographic_midpoint_multiple_points(self):
        """Test midpoint calculation with multiple diverse points."""
        coords = [
            (40.7128, -74.0060),  # New York
            (34.0522, -118.2437),  # Los Angeles
            (41.8781, -87.6298),  # Chicago
            (29.7604, -95.3698),  # Houston
        ]
        # Expected values calculated using external reference implementation
        expected = [36.8889, -94.0756]
        result = calculate_geographic_midpoint(coords)
        self.assertAlmostEqual(result[0], expected[0], places=4)
        self.assertAlmostEqual(result[1], expected[1], places=4)

    def test_calculate_geographic_midpoint_antipodal_points(self):
        """Test midpoint calculation with antipodal points (opposite sides of Earth)."""
        coords = [(0, 0), (0, 180)]
        result = calculate_geographic_midpoint(coords)
        self.assertAlmostEqual(
            result[0], 0, places=5
        )  # Latitude should be near equator

        coords = [(90, 0), (-90, 0)]  # North and South poles
        result = calculate_geographic_midpoint(coords)
        # For antipodal points, we expect the longitude to be somewhat arbitrary
        # but latitude should be close to 0 (equator)
        self.assertAlmostEqual(abs(result[0]), 0, places=5)

    def test_calculate_geographic_midpoint_international_date_line(self):
        """Test midpoint calculation across the international date line."""
        coords = [(45, 170), (45, -170)]
        result = calculate_geographic_midpoint(coords)
        self.assertAlmostEqual(result[0], 45, places=5)  # Latitude remains the same
        # 180 or -180 are equivalent for this test
        self.assertTrue(abs(abs(result[1]) - 180) < 0.00001)

    def test_calculate_geographic_midpoint_poles(self):
        """Test midpoint calculation involving poles."""
        coords = [(90, 0), (0, 0)]  # North pole and equator
        result = calculate_geographic_midpoint(coords)
        expected = [45.0, 0.0]
        self.assertAlmostEqual(result[0], expected[0], places=5)
        self.assertAlmostEqual(result[1], expected[1], places=5)

    def test_calculate_geographic_midpoint_empty_list(self):
        """Test providing an empty list of coordinates."""
        with self.assertRaises(DataValidationError):
            calculate_geographic_midpoint([])

    def test_calculate_geographic_midpoint_single_point(self):
        """Test midpoint calculation with a single point."""
        coords = [(45.0, -75.0)]
        expected = [45.0, -75.0]
        result = calculate_geographic_midpoint(coords)
        self.assertAlmostEqual(result[0], expected[0], places=5)
        self.assertAlmostEqual(result[1], expected[1], places=5)

    def test_round_trip_conversion(self):
        """Test that converting to cartesian and back gives original coordinates."""
        original_coords = [(40.7128, -74.0060)]  # New York
        result = calculate_geographic_midpoint(original_coords)
        self.assertAlmostEqual(result[0], original_coords[0][0], places=5)
        self.assertAlmostEqual(result[1], original_coords[0][1], places=5)


if __name__ == "__main__":
    unittest.main()
