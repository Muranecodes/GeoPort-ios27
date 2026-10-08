"""
Spherical geometry utilities for coordinate calculations and destination projections.
"""

import math
from typing import Tuple

EARTH_RADIUS_METERS = 6371000.0

CARDINAL_BEARINGS = {
    "w": 0.0,          # North
    "s": 180.0,        # South
    "a": 270.0,        # West
    "d": 90.0,         # East
    "arrowup": 0.0,
    "arrowdown": 180.0,
    "arrowleft": 270.0,
    "arrowright": 90.0,
    "up": 0.0,
    "down": 180.0,
    "left": 270.0,
    "right": 90.0,
    "north": 0.0,
    "south": 180.0,
    "west": 270.0,
    "east": 90.0,
}


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculates the great-circle distance between two coordinates in meters.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return EARTH_RADIUS_METERS * c


def destination_point(
    lat: float, lng: float, bearing_degrees: float, distance_meters: float
) -> Tuple[float, float]:
    """
    Calculates destination coordinates given start point (lat, lng),
    bearing in degrees (0° = North, 90° = East, 180° = South, 270° = West),
    and distance in meters.
    """
    if distance_meters == 0:
        return lat, lng

    phi1 = math.radians(lat)
    lambda1 = math.radians(lng)
    theta = math.radians(bearing_degrees)
    delta = distance_meters / EARTH_RADIUS_METERS

    sin_phi1 = math.sin(phi1)
    cos_phi1 = math.cos(phi1)
    sin_delta = math.sin(delta)
    cos_delta = math.cos(delta)

    sin_phi2 = sin_phi1 * cos_delta + cos_phi1 * sin_delta * math.cos(theta)
    sin_phi2 = max(-1.0, min(1.0, sin_phi2))
    phi2 = math.asin(sin_phi2)

    y = math.sin(theta) * sin_delta * cos_phi1
    x = cos_delta - sin_phi1 * sin_phi2
    lambda2 = lambda1 + math.atan2(y, x)

    # Normalize longitude to [-180, 180]
    lambda2 = (lambda2 + 3.0 * math.pi) % (2.0 * math.pi) - math.pi

    return math.degrees(phi2), math.degrees(lambda2)


def get_bearing_for_direction(direction: str) -> float:
    """
    Maps directional keys ('w', 'a', 's', 'd', arrows) to compass bearing degrees.
    """
    key = str(direction).strip().lower()
    if key in CARDINAL_BEARINGS:
        return CARDINAL_BEARINGS[key]
    raise ValueError(f"Invalid direction: '{direction}'. Expected one of ['w', 'a', 's', 'd'].")


def calculate_step(
    lat: float,
    lng: float,
    direction: str,
    speed_kmh: float,
    duration_seconds: float = 1.0,
) -> Tuple[float, float, float]:
    """
    Computes displacement for duration_seconds at speed_kmh in direction.
    Returns (new_lat, new_lng, distance_meters).
    """
    if speed_kmh < 0:
        raise ValueError(f"Speed cannot be negative: {speed_kmh}")
    bearing = get_bearing_for_direction(direction)
    distance_meters = (speed_kmh / 3.6) * duration_seconds
    new_lat, new_lng = destination_point(lat, lng, bearing, distance_meters)
    return new_lat, new_lng, distance_meters


def calculate_bearing(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculates initial compass bearing in degrees (0° - 360°) from (lat1, lng1) to (lat2, lng2).
    0° = North, 90° = East, 180° = South, 270° = West.
    """
    if lat1 == lat2 and lng1 == lng2:
        return 0.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lng2 - lng1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)

    bearing_rad = math.atan2(y, x)
    return (math.degrees(bearing_rad) + 360.0) % 360.0


def calculate_polyline_distance(waypoints: list) -> float:
    """
    Calculates total great-circle distance along polyline waypoints in meters.
    """
    if not waypoints or len(waypoints) < 2:
        return 0.0
    total = 0.0
    for i in range(len(waypoints) - 1):
        total += haversine_distance(
            float(waypoints[i][0]), float(waypoints[i][1]),
            float(waypoints[i + 1][0]), float(waypoints[i + 1][1])
        )
    return total


def interpolate_polyline(waypoints: list, distance_meters: float) -> Tuple[float, float]:
    """
    Interpolates a coordinate at distance_meters along the polyline.
    If distance_meters <= 0, returns the first waypoint.
    If distance_meters >= total_distance, returns the final waypoint.
    """
    if not waypoints:
        raise ValueError("Waypoints list cannot be empty")
    if len(waypoints) == 1 or distance_meters <= 0:
        return float(waypoints[0][0]), float(waypoints[0][1])

    remaining = float(distance_meters)
    for i in range(len(waypoints) - 1):
        p1 = (float(waypoints[i][0]), float(waypoints[i][1]))
        p2 = (float(waypoints[i + 1][0]), float(waypoints[i + 1][1]))
        seg_dist = haversine_distance(p1[0], p1[1], p2[0], p2[1])
        if seg_dist <= 0:
            continue
        if remaining <= seg_dist:
            bearing = calculate_bearing(p1[0], p1[1], p2[0], p2[1])
            return destination_point(p1[0], p1[1], bearing, remaining)
        remaining -= seg_dist

    return float(waypoints[-1][0]), float(waypoints[-1][1])

