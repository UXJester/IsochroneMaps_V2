import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import pandas as pd
import json
from pathlib import Path
import folium
from src.maps import create_map
from src.utils.error_utils import DataAccessError, GeoJSONError

# Add the project root to path to allow importing from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMapGeneration(unittest.TestCase):
    """Test suite for map generation functionality"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Sample centers DataFrame
        self.centers_df = pd.DataFrame(
            {
                "id": [1, 2],
                "name": ["Test City 1", "Test City 2"],
                "city": ["San Francisco", "New York"],
                "state": ["CA", "NY"],
                "zip_code": ["94105", "10001"],
                "latitude": [37.7749, 40.7128],
                "longitude": [-122.4194, -74.006],
            }
        )

        # Sample locations DataFrame
        self.locations_df = pd.DataFrame(
            {
                "id": [1, 2],
                "name": ["Location 1", "Location 2"],
                "address": ["123 Main St", "456 Broadway"],
                "city": ["San Francisco", "New York"],
                "state": ["CA", "NY"],
                "zip_code": ["94105", "10001"],
                "latitude": [37.77, 40.71],
                "longitude": [-122.42, -74.01],
            }
        )

        # Sample isochrones GeoJSON
        self.isochrones_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": "Test City 1", "value": 3600},  # 60 minutes
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-122.4194, 37.7749],
                                [-122.4294, 37.7849],
                                [-122.4094, 37.7749],
                                [-122.4194, 37.7749],
                            ]
                        ],
                    },
                },
                {
                    "type": "Feature",
                    "properties": {"name": "Test City 2", "value": 1800},  # 30 minutes
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-74.006, 40.7128],
                                [-74.016, 40.7228],
                                [-73.996, 40.7128],
                                [-74.006, 40.7128],
                            ]
                        ],
                    },
                },
            ],
        }

        # Feature colors mapping
        self.feature_colors = {"Test City 1": "#1f77b4", "Test City 2": "#ff7f0e"}

        # Map center coordinates
        self.map_center = [39.0, -98.0]

        # Mock config for tables
        self.mock_tables = {
            "centers": {"table_name": "centers", "columns": {"city": "name"}},
            "locations": {"table_name": "locations", "columns": {"name": "name"}},
        }

        # Create patches for configuration
        self.map_settings_patch = patch(
            "src.maps.MAP_SETTINGS",
            {
                "zoom": 10,
                "min_zoom": 5,
                "max_zoom": 12,
                "colors": ["#1f77b4", "#ff7f0e"],
                "layers": {
                    "draw": {"name": "Draw Layer", "show": True},
                    "isochrones": {"name": "Isochrones", "show": True},
                    "centers": {"name": "Centers", "show": True},
                    "locations": {"name": "Locations", "show": False},
                },
                "tiles": {
                    "default": "OpenStreetMap",
                    "preferred": "CartoDB",
                    "providers": {
                        "OpenStreetMap": {"name": "OpenStreetMap"},
                        "CartoDB": {"name": "CartoDB Positron"},
                        "Satellite": {
                            "tiles": "https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
                            "attr": "© Google",
                            "name": "Google Satellite",
                        },
                    },
                },
            },
        )

        self.tables_patch = patch("src.maps.TABLES", self.mock_tables)

        # Start patches
        self.map_settings = self.map_settings_patch.start()
        self.tables = self.tables_patch.start()

        # Mock file operations
        self.mock_css_open = patch(
            "pathlib.Path.open", mock_open(read_data="/* CSS content */")
        )
        self.mock_js_open = patch(
            "src.maps.Path.open", mock_open(read_data="/* JS content */")
        )
        self.mock_css_file = self.mock_css_open.start()
        self.mock_js_file = self.mock_js_open.start()

    def tearDown(self):
        """Clean up after each test method."""
        self.map_settings_patch.stop()
        self.tables_patch.stop()
        self.mock_css_open.stop()
        self.mock_js_open.stop()
        patch.stopall()

    def test_create_map_basic(self):
        """Test basic map creation with default parameters"""
        # Create the map
        result_map = create_map(
            self.centers_df,
            self.isochrones_geojson,
            self.feature_colors,
            self.map_center,
        )

        # Verify the map is created
        self.assertIsInstance(result_map, folium.Map)

        # Check basic map properties
        self.assertEqual(result_map.location, self.map_center)
        self.assertEqual(result_map.options["zoom"], 10)

        # Check min_zoom and max_zoom through get_bounds() which uses these values
        # or through direct attribute access if available in this version
        if hasattr(result_map, "_min_zoom"):
            self.assertEqual(result_map._min_zoom, 5)
            self.assertEqual(result_map._max_zoom, 12)
        else:
            # Skip these assertions if the attributes aren't available in this folium version
            self.skipTest(
                "min_zoom and max_zoom attributes not available in this folium version"
            )

        # Verify all the expected elements are added to the map
        self.assertEqual(
            len(result_map._children), 6
        )  # 4 layers + layer control + macro element

    def test_create_map_custom_tile_provider(self):
        """Test map creation with a custom tile provider"""
        # Create map with custom tile provider
        result_map = create_map(
            self.centers_df,
            self.isochrones_geojson,
            self.feature_colors,
            self.map_center,
            tile_provider="Satellite",
        )

        # Verify the map is created with the correct tile provider
        self.assertIsInstance(result_map, folium.Map)

        # Find the tile layer in the map's children
        tile_layers = [
            child
            for child in result_map._children.values()
            if isinstance(child, folium.TileLayer)
        ]

        # Should have a custom tile layer for Satellite
        self.assertGreaterEqual(len(tile_layers), 1)

        # Check if any tile layer is using the expected Satellite URL
        satellite_layer = next(
            (
                layer
                for layer in tile_layers
                if hasattr(layer, "tiles") and "google.com/vt/lyrs=s" in layer.tiles
            ),
            None,
        )

        self.assertIsNotNone(satellite_layer)

    def test_create_map_all_tile_layers(self):
        """Test map creation with all tile layers included"""
        # Create map with all tile providers
        result_map = create_map(
            self.centers_df,
            self.isochrones_geojson,
            self.feature_colors,
            self.map_center,
            include_all_tiles=True,
        )

        # Verify the map includes multiple tile layers
        tile_layers = [
            child
            for child in result_map._children.values()
            if isinstance(child, folium.TileLayer)
        ]

        # Should have multiple tile layers
        self.assertGreaterEqual(len(tile_layers), 2)

        # Check for layer control to switch between tile layers
        layer_controls = [
            child
            for child in result_map._children.values()
            if isinstance(child, folium.LayerControl)
        ]
        self.assertEqual(len(layer_controls), 1)

    @patch("src.maps.LogContext")
    def test_create_map_isochrones(self, mock_log_context):
        """Test that isochrones are properly added to the map"""
        # Create the map
        result_map = create_map(
            self.centers_df,
            self.isochrones_geojson,
            self.feature_colors,
            self.map_center,
        )

        # Find the isochrones layer in the map's children
        feature_groups = [
            child
            for child in result_map._children.values()
            if isinstance(child, folium.FeatureGroup)
        ]

        isochrone_layer = next(
            (layer for layer in feature_groups if layer.layer_name == "Isochrones"),
            None,
        )

        self.assertIsNotNone(isochrone_layer)

        # Verify GeoJSON features are added to the isochrone layer
        geojson_features = [
            child
            for child in isochrone_layer._children.values()
            if isinstance(child, folium.GeoJson)
        ]

        # Should have 2 GeoJSON features (one for each city)
        self.assertEqual(len(geojson_features), 2)

    def test_create_map_center_markers(self):
        """Test that center markers are properly added to the map"""
        # Create the map
        result_map = create_map(
            self.centers_df,
            self.isochrones_geojson,
            self.feature_colors,
            self.map_center,
        )

        # Find the centers layer in the map's children
        feature_groups = [
            child
            for child in result_map._children.values()
            if isinstance(child, folium.FeatureGroup)
        ]

        centers_layer = next(
            (layer for layer in feature_groups if layer.layer_name == "Centers"), None
        )

        self.assertIsNotNone(centers_layer)

        # Verify markers are added to the centers layer
        markers = [
            child
            for child in centers_layer._children.values()
            if isinstance(child, folium.Marker)
        ]

        # Should have 2 markers (one for each city)
        self.assertEqual(len(markers), 2)

        # Verify marker locations match center coordinates
        marker_locations = [marker.location for marker in markers]
        expected_locations = [
            [self.centers_df.iloc[0]["latitude"], self.centers_df.iloc[0]["longitude"]],
            [self.centers_df.iloc[1]["latitude"], self.centers_df.iloc[1]["longitude"]],
        ]

        for location in expected_locations:
            self.assertIn(location, marker_locations)

    def test_create_map_with_locations(self):
        """Test map with location markers included"""
        # Create map with locations
        result_map = create_map(
            self.centers_df,
            self.isochrones_geojson,
            self.feature_colors,
            self.map_center,
            include_locations=True,
            locations_df=self.locations_df,
        )

        # Find the locations layer in the map's children
        feature_groups = [
            child
            for child in result_map._children.values()
            if isinstance(child, folium.FeatureGroup)
        ]

        locations_layer = next(
            (layer for layer in feature_groups if layer.layer_name == "Locations"), None
        )

        self.assertIsNotNone(locations_layer)

        # Verify markers are added to the locations layer
        markers = [
            child
            for child in locations_layer._children.values()
            if isinstance(child, folium.Marker)
        ]

        # Should have 2 markers (one for each location)
        self.assertEqual(len(markers), 2)

        # Verify marker locations match location coordinates
        marker_locations = [marker.location for marker in markers]
        expected_locations = [
            [
                self.locations_df.iloc[0]["latitude"],
                self.locations_df.iloc[0]["longitude"],
            ],
            [
                self.locations_df.iloc[1]["latitude"],
                self.locations_df.iloc[1]["longitude"],
            ],
        ]

        for location in expected_locations:
            self.assertIn(location, marker_locations)

    def test_create_map_invalid_location_coordinates(self):
        """Test map with some invalid location coordinates"""
        # Create locations DataFrame with NaN coordinates
        locations_with_nan = self.locations_df.copy()
        locations_with_nan.at[0, "latitude"] = None

        # Create map with locations including invalid coordinates
        result_map = create_map(
            self.centers_df,
            self.isochrones_geojson,
            self.feature_colors,
            self.map_center,
            include_locations=True,
            locations_df=locations_with_nan,
        )

        # Find the locations layer in the map's children
        feature_groups = [
            child
            for child in result_map._children.values()
            if isinstance(child, folium.FeatureGroup)
        ]

        locations_layer = next(
            (layer for layer in feature_groups if layer.layer_name == "Locations"), None
        )

        self.assertIsNotNone(locations_layer)

        # Verify only valid markers are added to the locations layer
        markers = [
            child
            for child in locations_layer._children.values()
            if isinstance(child, folium.Marker)
        ]

        # Should have 1 marker (only the valid location)
        self.assertEqual(len(markers), 1)

        # Verify marker location matches the valid coordinates
        self.assertEqual(
            markers[0].location,
            [
                self.locations_df.iloc[1]["latitude"],
                self.locations_df.iloc[1]["longitude"],
            ],
        )

    def test_create_map_custom_layers(self):
        """Test map with custom layer configuration"""
        # Create a custom MAP_SETTINGS with modified layer settings
        custom_settings = {
            "zoom": 10,
            "min_zoom": 5,
            "max_zoom": 12,
            "colors": ["#1f77b4", "#ff7f0e"],
            "layers": {
                "draw": {"name": "Custom Draw", "show": False},
                "isochrones": {"name": "Custom Isochrones", "show": True},
                "centers": {"name": "Custom Centers", "show": False},
                "locations": {"name": "Custom Locations", "show": True},
            },
            "tiles": {
                "default": "OpenStreetMap",
                "providers": {"OpenStreetMap": {"name": "OpenStreetMap"}},
            },
        }

        with patch("src.maps.MAP_SETTINGS", custom_settings):
            # Create map with custom layer settings
            result_map = create_map(
                self.centers_df,
                self.isochrones_geojson,
                self.feature_colors,
                self.map_center,
                include_locations=True,
                locations_df=self.locations_df,
            )

            # Find the feature groups in the map's children
            feature_groups = [
                child
                for child in result_map._children.values()
                if isinstance(child, folium.FeatureGroup)
            ]

            # Verify layer names match custom settings
            layer_names = {layer.layer_name for layer in feature_groups}
            expected_names = {
                "Custom Draw",
                "Custom Isochrones",
                "Custom Centers",
                "Custom Locations",
            }
            self.assertEqual(layer_names, expected_names)

            # Verify layer visibility matches custom settings
            draw_layer = next(
                layer for layer in feature_groups if layer.layer_name == "Custom Draw"
            )
            isochrones_layer = next(
                layer
                for layer in feature_groups
                if layer.layer_name == "Custom Isochrones"
            )
            centers_layer = next(
                layer
                for layer in feature_groups
                if layer.layer_name == "Custom Centers"
            )
            locations_layer = next(
                layer
                for layer in feature_groups
                if layer.layer_name == "Custom Locations"
            )

            self.assertEqual(draw_layer.show, False)
            self.assertEqual(isochrones_layer.show, True)
            self.assertEqual(centers_layer.show, False)
            self.assertEqual(locations_layer.show, True)


if __name__ == "__main__":
    unittest.main()
