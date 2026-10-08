import math
import sys
import unittest
from pathlib import Path

# Ensure src is in python path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from geometry import (
    haversine_distance,
    destination_point,
    get_bearing_for_direction,
    calculate_step,
    CARDINAL_BEARINGS,
    EARTH_RADIUS_METERS,
)
from location_sink import LocationSink, MockLocationSink, DvtLocationSink
import main


class TestGeometryUtilities(unittest.TestCase):
    def test_haversine_distance_same_coordinates(self):
        dist = haversine_distance(25.0330, 121.5654, 25.0330, 121.5654)
        self.assertAlmostEqual(dist, 0.0, places=5)

    def test_haversine_distance_known_distance(self):
        # 1 degree of latitude is approximately 111,195 meters (using R=6371000)
        expected_m = (math.pi / 180.0) * EARTH_RADIUS_METERS
        dist = haversine_distance(0.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(dist, expected_m, delta=1.0)

    def test_cardinal_bearings_mapping(self):
        # 'w' = North (0°), 'a' = West (270°), 's' = South (180°), 'd' = East (90°)
        self.assertEqual(get_bearing_for_direction("w"), 0.0)
        self.assertEqual(get_bearing_for_direction("W"), 0.0)
        self.assertEqual(get_bearing_for_direction("s"), 180.0)
        self.assertEqual(get_bearing_for_direction("S"), 180.0)
        self.assertEqual(get_bearing_for_direction("a"), 270.0)
        self.assertEqual(get_bearing_for_direction("A"), 270.0)
        self.assertEqual(get_bearing_for_direction("d"), 90.0)
        self.assertEqual(get_bearing_for_direction("D"), 90.0)

        with self.assertRaises(ValueError):
            get_bearing_for_direction("invalid_dir")

    def test_destination_point_north(self):
        # Stepping North: latitude increases, longitude unchanged
        start_lat, start_lng = 25.0330, 121.5654
        distance = 100.0  # 100 meters
        new_lat, new_lng = destination_point(start_lat, start_lng, bearing_degrees=0.0, distance_meters=distance)
        self.assertGreater(new_lat, start_lat)
        self.assertAlmostEqual(new_lng, start_lng, places=5)

        actual_dist = haversine_distance(start_lat, start_lng, new_lat, new_lng)
        self.assertAlmostEqual(actual_dist, distance, places=3)

    def test_destination_point_south(self):
        # Stepping South: latitude decreases, longitude unchanged
        start_lat, start_lng = 25.0330, 121.5654
        distance = 100.0
        new_lat, new_lng = destination_point(start_lat, start_lng, bearing_degrees=180.0, distance_meters=distance)
        self.assertLess(new_lat, start_lat)
        self.assertAlmostEqual(new_lng, start_lng, places=5)

        actual_dist = haversine_distance(start_lat, start_lng, new_lat, new_lng)
        self.assertAlmostEqual(actual_dist, distance, places=3)

    def test_destination_point_east(self):
        # Stepping East: latitude roughly unchanged, longitude increases
        start_lat, start_lng = 25.0330, 121.5654
        distance = 100.0
        new_lat, new_lng = destination_point(start_lat, start_lng, bearing_degrees=90.0, distance_meters=distance)
        self.assertAlmostEqual(new_lat, start_lat, places=4)
        self.assertGreater(new_lng, start_lng)

        actual_dist = haversine_distance(start_lat, start_lng, new_lat, new_lng)
        self.assertAlmostEqual(actual_dist, distance, places=3)

    def test_destination_point_west(self):
        # Stepping West: latitude roughly unchanged, longitude decreases
        start_lat, start_lng = 25.0330, 121.5654
        distance = 100.0
        new_lat, new_lng = destination_point(start_lat, start_lng, bearing_degrees=270.0, distance_meters=distance)
        self.assertAlmostEqual(new_lat, start_lat, places=4)
        self.assertLess(new_lng, start_lng)

        actual_dist = haversine_distance(start_lat, start_lng, new_lat, new_lng)
        self.assertAlmostEqual(actual_dist, distance, places=3)

    def test_calculate_step_various_speeds(self):
        # Walking: 5 km/h -> 5 / 3.6 ≈ 1.388889 meters
        lat, lng, dist = calculate_step(0.0, 0.0, "w", speed_kmh=5.0)
        self.assertAlmostEqual(dist, 5.0 / 3.6, places=5)
        self.assertAlmostEqual(haversine_distance(0.0, 0.0, lat, lng), 5.0 / 3.6, places=4)

        # Cycling: 20 km/h -> 20 / 3.6 ≈ 5.555556 meters
        lat, lng, dist = calculate_step(0.0, 0.0, "d", speed_kmh=20.0)
        self.assertAlmostEqual(dist, 20.0 / 3.6, places=5)
        self.assertAlmostEqual(haversine_distance(0.0, 0.0, lat, lng), 20.0 / 3.6, places=4)

        # Driving: 60 km/h -> 60 / 3.6 ≈ 16.666667 meters
        lat, lng, dist = calculate_step(0.0, 0.0, "s", speed_kmh=60.0)
        self.assertAlmostEqual(dist, 60.0 / 3.6, places=5)
        self.assertAlmostEqual(haversine_distance(0.0, 0.0, lat, lng), 60.0 / 3.6, places=4)


    def test_destination_point_zero_distance(self):
        lat, lng = destination_point(12.34, 56.78, bearing_degrees=90.0, distance_meters=0.0)
        self.assertEqual(lat, 12.34)
        self.assertEqual(lng, 56.78)

    def test_destination_point_antimeridian_wrap(self):
        # Starting near 179.999° East, stepping East crosses 180° into negative longitude
        lat, lng = destination_point(0.0, 179.999, bearing_degrees=90.0, distance_meters=1000.0)
        self.assertAlmostEqual(lat, 0.0, places=4)
        self.assertLess(lng, 0.0)
        self.assertGreaterEqual(lng, -180.0)

    def test_calculate_step_negative_speed_raises(self):
        with self.assertRaises(ValueError):
            calculate_step(0.0, 0.0, "w", speed_kmh=-5.0)


class TestLocationSink(unittest.TestCase):
    def test_mock_location_sink(self):
        sink = MockLocationSink()
        self.assertEqual(sink.locations, [])
        self.assertIsNone(sink.last_location)

        sink.set_location(25.0, 121.0)
        self.assertEqual(len(sink.locations), 1)
        self.assertEqual(sink.last_location, (25.0, 121.0))

        sink.set_location(25.001, 121.001)
        self.assertEqual(len(sink.locations), 2)
        self.assertEqual(sink.last_location, (25.001, 121.001))

        self.assertFalse(sink.cleared)
        sink.clear_location()
        self.assertTrue(sink.cleared)

        sink.reset()
        self.assertEqual(sink.locations, [])
        self.assertFalse(sink.cleared)

    def test_dvt_location_sink_delegation(self):
        dispatched = []
        cleared = []

        sink = DvtLocationSink(
            dispatch_fn=lambda lat, lng: dispatched.append((lat, lng)),
            clear_fn=lambda: cleared.append(True)
        )

        sink.set_location(37.7749, -122.4194)
        self.assertEqual(dispatched, [(37.7749, -122.4194)])

        sink.clear_location()
        self.assertEqual(cleared, [True])


class TestMoveStepEndpoint(unittest.TestCase):
    def setUp(self):
        self.app = main.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.mock_sink = MockLocationSink()
        main.set_location_sink(self.mock_sink)

    def tearDown(self):
        if hasattr(self.app, "navigation_controller"):
            delattr(self.app, "navigation_controller")

    def test_move_step_without_location_returns_400(self):
        main.location = None
        response = self.client.post("/move_step", json={"direction": "w", "speed_kmh": 5.0})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_move_step_empty_or_non_json_returns_400(self):
        main.location = "25.0330 121.5654"
        response = self.client.post("/move_step", data="non-json content", content_type="text/plain")
        self.assertEqual(response.status_code, 400)

    def test_move_step_invalid_direction_returns_400(self):
        main.location = "25.0330 121.5654"
        response = self.client.post("/move_step", json={"direction": "invalid", "speed_kmh": 5.0})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_move_step_invalid_speed_returns_400(self):
        main.location = "25.0330 121.5654"
        response = self.client.post("/move_step", json={"direction": "w", "speed_kmh": -10.0})
        self.assertEqual(response.status_code, 400)

        response = self.client.post("/move_step", json={"direction": "w", "speed_kmh": "not_a_number"})
        self.assertEqual(response.status_code, 400)

        # In Ticket 03, omitting speed_kmh falls back to active speed state
        response = self.client.post("/move_step", json={"direction": "w"})
        self.assertEqual(response.status_code, 200)

    def test_move_step_north_dispatches_and_updates_location(self):
        start_lat = 25.0330
        start_lng = 121.5654
        main.location = f"{start_lat} {start_lng}"
        speed_kmh = 36.0  # 10 m/s

        response = self.client.post("/move_step", json={"direction": "w", "speed_kmh": speed_kmh})
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("lat", data)
        self.assertIn("lng", data)
        self.assertIn("distance_m", data)
        self.assertAlmostEqual(data["distance_m"], 10.0, places=5)
        self.assertGreater(data["lat"], start_lat)
        self.assertAlmostEqual(data["lng"], start_lng, places=5)

        # Check that location sink received the dispatched location
        self.assertEqual(len(self.mock_sink.locations), 1)
        self.assertEqual(self.mock_sink.last_location, (data["lat"], data["lng"]))

        # Check that server's main.location is updated
        self.assertEqual(main.location, f"{data['lat']} {data['lng']}")

    def test_move_step_all_cardinal_directions(self):
        start_lat = 25.0330
        start_lng = 121.5654
        speed_kmh = 18.0  # 5 m/s

        # Test South
        main.location = f"{start_lat} {start_lng}"
        res_s = self.client.post("/move_step", json={"direction": "s", "speed_kmh": speed_kmh})
        self.assertEqual(res_s.status_code, 200)
        self.assertLess(res_s.get_json()["lat"], start_lat)

        # Test East
        main.location = f"{start_lat} {start_lng}"
        res_d = self.client.post("/move_step", json={"direction": "d", "speed_kmh": speed_kmh})
        self.assertEqual(res_d.status_code, 200)
        self.assertGreater(res_d.get_json()["lng"], start_lng)

        # Test West
        main.location = f"{start_lat} {start_lng}"
        res_a = self.client.post("/move_step", json={"direction": "a", "speed_kmh": speed_kmh})
        self.assertEqual(res_a.status_code, 200)
        self.assertLess(res_a.get_json()["lng"], start_lng)

    def test_move_step_speed_presets(self):
        start_lat, start_lng = 25.0330, 121.5654

        # Walking 5 km/h
        main.location = f"{start_lat} {start_lng}"
        res = self.client.post("/move_step", json={"direction": "w", "speed_kmh": 5.0})
        self.assertEqual(res.status_code, 200)
        self.assertAlmostEqual(res.get_json()["distance_m"], 5.0 / 3.6, places=4)

        # Cycling 20 km/h
        main.location = f"{start_lat} {start_lng}"
        res = self.client.post("/move_step", json={"direction": "w", "speed_kmh": 20.0})
        self.assertEqual(res.status_code, 200)
        self.assertAlmostEqual(res.get_json()["distance_m"], 20.0 / 3.6, places=4)

        # Driving 60 km/h
        main.location = f"{start_lat} {start_lng}"
        res = self.client.post("/move_step", json={"direction": "w", "speed_kmh": 60.0})
        self.assertEqual(res.status_code, 200)
        self.assertAlmostEqual(res.get_json()["distance_m"], 60.0 / 3.6, places=4)

    def test_move_step_with_provided_coordinates(self):
        # Endpoint can also accept 'lat' and 'lng' in request body
        main.location = None
        speed_kmh = 36.0
        response = self.client.post(
            "/move_step",
            json={"direction": "w", "speed_kmh": speed_kmh, "lat": 10.0, "lng": 20.0}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertGreater(data["lat"], 10.0)
        self.assertEqual(self.mock_sink.last_location, (data["lat"], data["lng"]))

    def test_move_step_interrupts_active_navigation(self):
        class DummyNavigationController:
            def __init__(self):
                self.stopped = False

            def stop(self):
                self.stopped = True

        dummy_controller = DummyNavigationController()
        self.app.navigation_controller = dummy_controller

        main.location = "25.0330 121.5654"
        response = self.client.post("/move_step", json={"direction": "w", "speed_kmh": 5.0})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(dummy_controller.stopped)

    def test_set_location_delegates_to_sink(self):
        main.location = "35.6762 139.6503"
        response = self.client.post("/set_location")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.mock_sink.last_location, (35.6762, 139.6503))


if __name__ == "__main__":
    unittest.main()
