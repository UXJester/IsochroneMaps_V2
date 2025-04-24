# This util isn't used in the codebase yet, but it is a placeholder for future use.
# """
# Geospatial Utility Functions
# =========================

# This module contains utility functions for working with geospatial data.

# Functions:
#     get_isochrones: Get isochrone polygons from OpenRouteService API.
#     calculate_accessibility_score: Calculate accessibility scores for locations.

# Example:
#     >>> from src.utils.geo_utils import get_isochrones
#     >>> from src.utils.client_utils import get_ors_client
#     >>> client = get_ors_client()
#     >>> isochrones = get_isochrones(client, longitude=-122.4194, latitude=37.7749,
#     ...                            travel_time=[5, 10, 15], profile="cycling-regular")
# """

# import requests
# import json
# from typing import List, Dict, Any


# def get_isochrones(
#     client: Any, longitude: float, latitude: float, travel_time: List[int], profile: str
# ) -> Dict[str, Any]:
#     """
#     Get isochrone polygons from OpenRouteService API.

#     Parameters:
#         client (Any): The OpenRouteService client.
#         longitude (float): The longitude of the location.
#         latitude (float): The latitude of the location.
#         travel_time (List[int]): List of travel times in minutes.
#         profile (str): The profile for the isochrone calculation (e.g., 'cycling-regular').

#     Returns:
#         Dict[str, Any]: The isochrone polygons.
#     """
#     coordinates = [[longitude, latitude]]
#     params = {
#         "locations": coordinates,
#         "range": travel_time,
#         "profile": profile,
#         "range_type": "time",
#     }
#     response = client.isochrones(**params)
#     return response


# def calculate_accessibility_score(
#     isochrones: Dict[str, Any], weights: List[float]
# ) -> float:
#     """
#     Calculate accessibility scores for locations.

#     Parameters:
#         isochrones (Dict[str, Any]): The isochrone polygons.
#         weights (List[float]): The weights for each isochrone polygon.

#     Returns:
#         float: The accessibility score.
#     """
#     score = 0.0
#     for isochrone, weight in zip(isochrones["features"], weights):
#         score += isochrone["properties"]["value"] * weight
#     return score
