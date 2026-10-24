import json
import math
import subprocess
import sys
import time
import unittest
from pathlib import Path

# Ensure src is in python path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import main
from geometry import (
    calculate_bearing,
    calculate_polyline_distance,
    destination_point,
    haversine_distance,
    interpolate_polyline,
)
from location_sink import MockLocationSink
from navigation_engine import NavigationController


class FakeClock:
    """Deterministic monotonic clock test double."""

    def __init__(self, start_time: float = 1000.0) -> None:
        self._time = float(start_time)

    def __call__(self) -> float:
        return self._time

    def advance(self, seconds: float) -> float:
        self._time += float(seconds)
        return self._time


class TestNavigationControllerAuthoritativeState(unittest.TestCase):
    def setUp(self):
        self.mock_sink = MockLocationSink()
        self.clock = FakeClock(1000.0)
        self.controller = NavigationController(
            sink=self.mock_sink,
            clock=self.clock,
            min_step_interval=0.95,
        )

    def tearDown(self):
        self.controller.stop()

    def test_initial_state(self):
        """Initial state tracks has_location=False and current coords 0.0."""
        self.assertFalse(self.controller.has_location)
        self.assertIsNone(self.controller.get_location_coords())
        self.assertEqual(self.controller.get_speed(), 5.0)

        status = self.controller.get_status()
        self.assertFalse(status["active"])
        self.assertFalse(status["paused"])
        self.assertFalse(status["completed"])
        self.assertEqual(status["current_lat"], 0.0)
        self.assertEqual(status["current_lng"], 0.0)
        self.assertEqual(status["speed_kmh"], 5.0)

    def test_set_and_get_location_coords(self):
        """set_location_coords sets coords and has_location without dispatching to sink."""
        res = self.controller.set_location_coords(25.0330, 121.5654)
        self.assertEqual(res, (25.0330, 121.5654))
        self.assertTrue(self.controller.has_location)
        self.assertEqual(self.controller.get_location_coords(), (25.0330, 121.5654))
        self.assertEqual(self.mock_sink.call_count, 0)

        status = self.controller.get_status()
        self.assertEqual(status["current_lat"], 25.0330)
        self.assertEqual(status["current_lng"], 121.5654)

    def test_set_location_coords_at_origin_sets_has_location(self):
        """Explicit (0.0, 0.0) sets has_location=True."""
        res = self.controller.set_location_coords(0.0, 0.0)
        self.assertEqual(res, (0.0, 0.0))
        self.assertTrue(self.controller.has_location)
        self.assertEqual(self.controller.get_location_coords(), (0.0, 0.0))

    def test_set_location_coords_bounds_validation(self):
        """Coordinates outside bounds or non-numeric raise ValueError."""
        with self.assertRaises(ValueError):
            self.controller.set_location_coords(95.0, 100.0)
        with self.assertRaises(ValueError):
            self.controller.set_location_coords(-95.0, 100.0)
        with self.assertRaises(ValueError):
            self.controller.set_location_coords(0.0, 185.0)
        with self.assertRaises(ValueError):
            self.controller.set_location_coords(0.0, -185.0)
        with self.assertRaises(ValueError):
            self.controller.set_location_coords("invalid", 100.0)
        with self.assertRaises(ValueError):
            self.controller.set_location_coords(float("nan"), 100.0)
        with self.assertRaises(ValueError):
            self.controller.set_location_coords(10.0, float("inf"))

    def test_set_location_coords_does_not_interrupt_active_nav(self):
        """set_location_coords preserves active auto navigation."""
        p1 = (25.0330, 121.5654)
        p2 = (25.0400, 121.5654)
        self.controller.start([p1, p2], speed_kmh=10.0)
        self.assertTrue(self.controller.active)

        self.controller.set_location_coords(25.0350, 121.5654)
        self.assertTrue(self.controller.active)

    def test_dispatch_current_location_without_location_raises(self):
        """dispatch_current_location raises ValueError if location has not been set."""
        with self.assertRaises(ValueError) as ctx:
            self.controller.dispatch_current_location()
        self.assertIn("Location is not set", str(ctx.exception))

    def test_dispatch_current_location_success(self):
        """dispatch_current_location dispatches to sink and sets _last_dispatch_time."""
        self.controller.set_location_coords(25.0330, 121.5654)
        self.mock_sink.reset()

        dispatched = self.controller.dispatch_current_location()
        self.assertEqual(dispatched, (25.0330, 121.5654))
        self.assertEqual(self.mock_sink.call_count, 1)
        self.assertEqual(self.mock_sink.last_location, (25.0330, 121.5654))
        self.assertEqual(self.controller._last_dispatch_time, 1000.0)

    def test_get_speed_and_update_speed(self):
        """get_speed returns speed_kmh, update_speed validates and updates speed."""
        self.assertEqual(self.controller.get_speed(), 5.0)
        eta = self.controller.update_speed(15.0)
        self.assertEqual(self.controller.get_speed(), 15.0)
        self.assertEqual(eta, 0.0)

        with self.assertRaises(ValueError):
            self.controller.update_speed(0.0)
        with self.assertRaises(ValueError):
            self.controller.update_speed(-5.0)
        with self.assertRaises(ValueError):
            self.controller.update_speed("abc")


class TestNavigationControllerManualSteering(unittest.TestCase):
    def setUp(self):
        self.mock_sink = MockLocationSink()
        self.clock = FakeClock(1000.0)
        self.controller = NavigationController(
            sink=self.mock_sink,
            clock=self.clock,
            min_step_interval=0.95,
        )

    def tearDown(self):
        self.controller.stop()

    def test_step_manual_requires_location(self):
        """step_manual raises ValueError if current location is not set and not provided."""
        with self.assertRaises(ValueError) as ctx:
            self.controller.step_manual("w")
        self.assertIn("Current location is not set", str(ctx.exception))

    def test_step_manual_with_coords_sets_location_and_steps(self):
        """step_manual with explicit lat/lng sets authoritative location and moves."""
        res = self.controller.step_manual("w", lat=25.0330, lng=121.5654)
        self.assertTrue(self.controller.has_location)
        self.assertGreater(res["distance_m"], 0.0)
        self.assertGreater(res["lat"], 25.0330)
        self.assertAlmostEqual(res["lng"], 121.5654, places=5)
        self.assertEqual(self.mock_sink.call_count, 1)
        self.assertEqual(self.mock_sink.last_location, (res["lat"], res["lng"]))
        self.assertEqual(self.controller._last_dispatch_time, 1000.0)

    def test_step_manual_partial_coords_raises(self):
        """Providing only one of lat/lng raises ValueError."""
        with self.assertRaises(ValueError):
            self.controller.step_manual("w", lat=25.0330)
        with self.assertRaises(ValueError):
            self.controller.step_manual("w", lng=121.5654)

    def test_step_manual_invalid_direction_raises(self):
        """Invalid direction keys raise ValueError."""
        self.controller.set_location_coords(25.0330, 121.5654)
        with self.assertRaises(ValueError):
            self.controller.step_manual("x")
        with self.assertRaises(ValueError):
            self.controller.step_manual("")

    def test_step_manual_cardinal_directions(self):
        """Directional keys (WASD, arrows, cardinal names) correctly compute displacements."""
        directions = ["w", "a", "s", "d", "arrowup", "arrowleft", "arrowdown", "arrowright", "north", "west", "south", "east"]
        for dir_key in directions:
            self.clock.advance(1.0)
            res = self.controller.step_manual(dir_key, lat=25.0330, lng=121.5654)
            self.assertGreater(res["distance_m"], 0.0)

    def test_step_manual_speed_override_does_not_mutate_speed_kmh(self):
        """Passing speed_kmh overrides step speed without altering controller.speed_kmh."""
        self.controller.set_location_coords(25.0330, 121.5654)
        self.controller.update_speed(5.0)

        self.clock.advance(1.0)
        # 36 km/h = 10 m/s displacement for 1s
        res = self.controller.step_manual("d", speed_kmh=36.0)
        self.assertAlmostEqual(res["distance_m"], 10.0, places=2)
        self.assertEqual(self.controller.get_speed(), 5.0)

    def test_step_manual_interrupts_active_auto_navigation(self):
        """Calling step_manual immediately halts running auto navigation."""
        p1 = (25.0330, 121.5654)
        p2 = (25.0400, 121.5654)
        self.controller.start([p1, p2], speed_kmh=10.0)
        self.assertTrue(self.controller.active)

        self.clock.advance(1.0)
        res = self.controller.step_manual("w")
        self.assertFalse(self.controller.active)
        self.assertGreater(res["distance_m"], 0.0)

    def test_step_manual_anti_burst_pacing_drops_rapid_steps(self):
        """Manual steps under min_step_interval (0.95s) are dropped without sink dispatch."""
        self.controller.set_location_coords(25.0330, 121.5654)

        # First step at t=1000.0 succeeds
        res1 = self.controller.step_manual("w")
        self.assertGreater(res1["distance_m"], 0.0)
        self.assertEqual(self.mock_sink.call_count, 1)
        lat1, lng1 = res1["lat"], res1["lng"]

        # Burst 1: advance 0.5s (< 0.95s) -> dropped
        self.clock.advance(0.5)
        res2 = self.controller.step_manual("w")
        self.assertEqual(res2["distance_m"], 0.0)
        self.assertEqual(res2["lat"], lat1)
        self.assertEqual(res2["lng"], lng1)
        self.assertEqual(self.mock_sink.call_count, 1)

        # Burst 2: advance 0.4s (total 0.9s from dispatch < 0.95s) -> dropped
        self.clock.advance(0.4)
        res3 = self.controller.step_manual("w")
        self.assertEqual(res3["distance_m"], 0.0)
        self.assertEqual(res3["lat"], lat1)
        self.assertEqual(res3["lng"], lng1)
        self.assertEqual(self.mock_sink.call_count, 1)

        # Step 4: advance 0.1s (total 1.0s >= 0.95s) -> succeeds
        self.clock.advance(0.1)
        res4 = self.controller.step_manual("w")
        self.assertGreater(res4["distance_m"], 0.0)
        self.assertGreater(res4["lat"], lat1)
        self.assertEqual(self.mock_sink.call_count, 2)
        self.assertEqual(self.controller._last_dispatch_time, 1001.0)

    def test_step_manual_anti_burst_after_auto_nav_start(self):
        """Auto nav start sets last_dispatch_time; immediate manual step is anti-burst paced."""
        p1 = (25.0330, 121.5654)
        p2 = (25.0400, 121.5654)
        self.controller.start([p1, p2], speed_kmh=10.0)
        self.assertEqual(self.controller._last_dispatch_time, 1000.0)
        self.assertEqual(self.mock_sink.call_count, 1)

        # Immediate manual step at t=1000.2 (0.2s later < 0.95s)
        self.clock.advance(0.2)
        res = self.controller.step_manual("w")
        # Auto nav stopped, displacement dropped
        self.assertFalse(self.controller.active)
        self.assertEqual(res["distance_m"], 0.0)
        self.assertEqual(self.mock_sink.call_count, 1)

        # Advance to t=1001.0 (1.0s >= 0.95s)
        self.clock.advance(0.8)
        res2 = self.controller.step_manual("w")
        self.assertGreater(res2["distance_m"], 0.0)
        self.assertEqual(self.mock_sink.call_count, 2)


class TestGeometryAndInterpolation(unittest.TestCase):
    def test_calculate_bearing_cardinals(self):
        """Cardinal bearings from equator origin (0, 0)."""
        # North
        self.assertAlmostEqual(calculate_bearing(0.0, 0.0, 1.0, 0.0), 0.0, places=2)
        # East
        self.assertAlmostEqual(calculate_bearing(0.0, 0.0, 0.0, 1.0), 90.0, places=2)
        # South
        self.assertAlmostEqual(calculate_bearing(0.0, 0.0, -1.0, 0.0), 180.0, places=2)
        # West
        self.assertAlmostEqual(calculate_bearing(0.0, 0.0, 0.0, -1.0), 270.0, places=2)
        # Identical point
        self.assertEqual(calculate_bearing(25.0, 121.0, 25.0, 121.0), 0.0)

    def test_calculate_polyline_distance(self):
        """Calculates cumulative distance across multiple waypoints."""
        self.assertEqual(calculate_polyline_distance([]), 0.0)
        self.assertEqual(calculate_polyline_distance([(25.0, 121.0)]), 0.0)

        p1 = (25.0330, 121.5654)
        p2 = (25.0340, 121.5654)
        p3 = (25.0340, 121.5670)

        dist12 = haversine_distance(p1[0], p1[1], p2[0], p2[1])
        dist23 = haversine_distance(p2[0], p2[1], p3[0], p3[1])

        total = calculate_polyline_distance([p1, p2, p3])
        self.assertAlmostEqual(total, dist12 + dist23, places=3)

    def test_interpolate_polyline_two_points(self):
        """Interpolates intermediate coordinates along a 2-point segment."""
        p1 = (25.0330, 121.5654)
        p2 = (25.0350, 121.5654)
        total_dist = haversine_distance(p1[0], p1[1], p2[0], p2[1])

        # At start
        start = interpolate_polyline([p1, p2], 0.0)
        self.assertAlmostEqual(start[0], p1[0], places=5)
        self.assertAlmostEqual(start[1], p1[1], places=5)

        # Negative distance clamped to start
        neg = interpolate_polyline([p1, p2], -10.0)
        self.assertEqual(neg, (p1[0], p1[1]))

        # Halfway
        half = interpolate_polyline([p1, p2], total_dist / 2.0)
        self.assertAlmostEqual(half[0], 25.0340, places=4)
        self.assertAlmostEqual(half[1], 121.5654, places=4)

        # At or beyond end
        end = interpolate_polyline([p1, p2], total_dist + 50.0)
        self.assertAlmostEqual(end[0], p2[0], places=5)
        self.assertAlmostEqual(end[1], p2[1], places=5)

    def test_interpolate_polyline_multi_segment(self):
        """Interpolates accurately across multi-segment turn paths."""
        p1 = (0.0, 0.0)
        p2 = (0.0, 1.0)  # East ~111.19 km
        p3 = (1.0, 1.0)  # North ~111.19 km

        d1 = haversine_distance(p1[0], p1[1], p2[0], p2[1])
        d2 = haversine_distance(p2[0], p2[1], p3[0], p3[1])

        # Query on first segment
        mid1 = interpolate_polyline([p1, p2, p3], d1 / 2.0)
        self.assertAlmostEqual(mid1[0], 0.0, places=3)
        self.assertAlmostEqual(mid1[1], 0.5, places=3)

        # Query on second segment
        mid2 = interpolate_polyline([p1, p2, p3], d1 + (d2 / 2.0))
        self.assertAlmostEqual(mid2[0], 0.5, places=3)
        self.assertAlmostEqual(mid2[1], 1.0, places=3)

        # Exceeding total
        finish = interpolate_polyline([p1, p2, p3], d1 + d2 + 500.0)
        self.assertAlmostEqual(finish[0], 1.0, places=5)
        self.assertAlmostEqual(finish[1], 1.0, places=5)

    def test_interpolate_empty_polyline_raises(self):
        """Empty polyline raises ValueError."""
        with self.assertRaises(ValueError):
            interpolate_polyline([], 50.0)


class TestNavigationControllerLifecycle(unittest.TestCase):
    def setUp(self):
        self.mock_sink = MockLocationSink()
        self.controller = NavigationController(sink=self.mock_sink, tick_interval=1.0)

    def tearDown(self):
        self.controller.stop()

    def test_start_initializes_state_without_immediate_tick(self):
        """Starting navigation initializes remaining distance and status without stepping."""
        p1 = (25.0330, 121.5654)
        p2 = (25.0340, 121.5654)
        result = self.controller.start([p1, p2], speed_kmh=18.0)  # 18 km/h = 5 m/s

        self.assertEqual(result["status"], "started")
        self.assertGreater(result["total_distance_m"], 100.0)
        self.assertGreater(result["estimated_duration_s"], 0.0)

        status = self.controller.get_status()
        self.assertTrue(status["active"])
        self.assertFalse(status["paused"])
        self.assertFalse(status["completed"])
        self.assertAlmostEqual(status["current_lat"], p1[0], places=5)
        self.assertAlmostEqual(status["current_lng"], p1[1], places=5)
        self.assertEqual(status["speed_kmh"], 18.0)

    def test_step_tick_advances_distance_and_updates_sink(self):
        """step_tick advances distance by speed / 3.6 meters and dispatches to sink."""
        p1 = (0.0, 0.0)
        p2 = (0.0, 1.0)
        total_dist = haversine_distance(p1[0], p1[1], p2[0], p2[1])

        # 36 km/h = 10 m/s
        self.controller.start([p1, p2], speed_kmh=36.0)
        self.mock_sink.reset()

        # Step 1 tick (1 second -> 10 meters)
        active = self.controller.step_tick(dt=1.0)
        self.assertTrue(active)
        self.assertEqual(self.mock_sink.call_count, 1)

        status = self.controller.get_status()
        self.assertAlmostEqual(status["remaining_distance_m"], total_dist - 10.0, delta=1.0)
        self.assertFalse(status["completed"])

    def test_arrival_at_destination_stops_and_marks_completed(self):
        """Reaching final destination dispatches final coordinate, halts worker, sets completed=True."""
        p1 = (25.0330, 121.5654)
        p2 = (25.0331, 121.5654)  # ~11.1 meters away
        total_dist = haversine_distance(p1[0], p1[1], p2[0], p2[1])

        # Speed 72 km/h = 20 m/s (reaches ~11m destination in 1 tick)
        self.controller.start([p1, p2], speed_kmh=72.0)
        self.mock_sink.reset()

        active = self.controller.step_tick(dt=1.0)
        self.assertFalse(active)

        status = self.controller.get_status()
        self.assertFalse(status["active"])
        self.assertTrue(status["completed"])
        self.assertEqual(status["remaining_distance_m"], 0.0)
        self.assertEqual(status["remaining_time_s"], 0.0)
        self.assertAlmostEqual(status["current_lat"], p2[0], places=5)
        self.assertAlmostEqual(status["current_lng"], p2[1], places=5)
        self.assertEqual(self.mock_sink.last_location, (p2[0], p2[1]))

    def test_pause_and_resume(self):
        """Paused navigation freezes advancement until resumed."""
        p1 = (0.0, 0.0)
        p2 = (0.0, 1.0)
        self.controller.start([p1, p2], speed_kmh=36.0)

        self.controller.pause()
        self.assertTrue(self.controller.paused)

        self.mock_sink.reset()
        # Stepping while paused does not advance
        self.controller.step_tick(dt=1.0)
        self.assertEqual(self.mock_sink.call_count, 0)
        self.assertEqual(self.controller.traveled_distance_m, 0.0)

        # Resume
        self.controller.resume()
        self.assertFalse(self.controller.paused)
        self.controller.step_tick(dt=1.0)
        self.assertEqual(self.mock_sink.call_count, 1)
        self.assertAlmostEqual(self.controller.traveled_distance_m, 10.0, delta=0.5)

    def test_update_speed_updates_eta(self):
        """Dynamically updating speed recalculates remaining ETA proportionally."""
        p1 = (0.0, 0.0)
        p2 = (0.0, 1.0)
        self.controller.start([p1, p2], speed_kmh=36.0)  # 10 m/s

        rem_dist = self.controller.remaining_distance_m
        old_eta = rem_dist / 10.0

        # Double the speed to 72 km/h (20 m/s) -> ETA halved
        new_eta = self.controller.update_speed(72.0)
        self.assertEqual(self.controller.speed_kmh, 72.0)
        self.assertAlmostEqual(new_eta, old_eta / 2.0, places=1)

    def test_invalid_parameters_raise(self):
        """Validates waypoints length, coordinate bounds, and positive speeds."""
        # Less than 2 waypoints
        with self.assertRaises(ValueError):
            self.controller.start([(25.0, 121.0)], speed_kmh=5.0)

        # Empty waypoints
        with self.assertRaises(ValueError):
            self.controller.start([], speed_kmh=5.0)

        # Non-numeric coordinate
        with self.assertRaises(ValueError):
            self.controller.start([["invalid", 121.0], [25.0, 121.0]], speed_kmh=5.0)

        # Out of bounds latitude
        with self.assertRaises(ValueError):
            self.controller.start([(95.0, 121.0), [25.0, 121.0]], speed_kmh=5.0)

        # Zero or negative speed
        with self.assertRaises(ValueError):
            self.controller.start([(25.0, 121.0), (25.1, 121.0)], speed_kmh=0.0)
        with self.assertRaises(ValueError):
            self.controller.start([(25.0, 121.0), (25.1, 121.0)], speed_kmh=-5.0)

    def test_background_worker_thread_runs_and_completes(self):
        """Worker thread ticks in background and completes autonomously."""
        fast_controller = NavigationController(
            sink=self.mock_sink,
            tick_interval=0.01  # fast ticks
        )
        p1 = (25.0330, 121.5654)
        p2 = (25.0331, 121.5654)  # ~11.1 meters away
        try:
            # 200 km/h reaches 11.1 meters in 1-2 ticks
            fast_controller.start([p1, p2], speed_kmh=200.0)
            self.assertTrue(fast_controller.active)

            # Wait deterministically for completion event
            completed = fast_controller._stop_event.wait(timeout=2.0)
            self.assertTrue(completed)

            status = fast_controller.get_status()
            self.assertFalse(status["active"])
            self.assertTrue(status["completed"])
            self.assertEqual(self.mock_sink.last_location, (p2[0], p2[1]))
        finally:
            fast_controller.stop()

    def test_worker_monotonic_clock_pacing_and_burst_prevention(self):
        """Monotonic clock pacing drops rapid bursts and preserves pacing deterministically."""
        clock = FakeClock(1000.0)
        pacing_controller = NavigationController(
            sink=self.mock_sink,
            clock=clock,
            min_step_interval=0.95,
        )
        p1 = (25.0330, 121.5654)
        p2 = (25.0400, 121.5654)
        try:
            # start() dispatches initial position and stamps clock
            pacing_controller.start([p1, p2], speed_kmh=5.0)
            self.assertEqual(pacing_controller._last_dispatch_time, 1000.0)
            self.assertEqual(self.mock_sink.call_count, 1)

            # Advance clock 1.0s and step tick
            clock.advance(1.0)
            active = pacing_controller.step_tick(dt=1.0)
            self.assertTrue(active)
            self.assertEqual(pacing_controller._last_dispatch_time, 1001.0)
            self.assertEqual(self.mock_sink.call_count, 2)

            # Immediate manual step attempt without clock advancing is dropped by anti-burst
            res = pacing_controller.step_manual("w")
            self.assertEqual(res["distance_m"], 0.0)
            self.assertEqual(self.mock_sink.call_count, 2)

            # Advance 0.95s -> next step succeeds
            clock.advance(0.95)
            res2 = pacing_controller.step_manual("w")
            self.assertGreater(res2["distance_m"], 0.0)
            self.assertEqual(self.mock_sink.call_count, 3)
            self.assertEqual(pacing_controller._last_dispatch_time, 1001.95)
        finally:
            pacing_controller.stop()



class TestNavigationFlaskEndpoints(unittest.TestCase):
    def setUp(self):
        self.app = main.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.mock_sink = MockLocationSink()
        main.set_location_sink(self.mock_sink)
        main.set_current_speed(5.0)

        # Attach test navigation controller
        self.test_controller = NavigationController(
            sink_provider=main.get_location_sink,
            tick_interval=1.0
        )
        self.app.navigation_controller = self.test_controller

    def tearDown(self):
        if hasattr(self.app, "navigation_controller") and self.app.navigation_controller:
            self.app.navigation_controller.stop()
        main.set_current_speed(5.0)

    def test_start_navigation_endpoint_success(self):
        """POST /start_navigation starts controller and returns 200 with distance and ETA."""
        waypoints = [
            [25.0330, 121.5654],
            [25.0350, 121.5654]
        ]
        response = self.client.post("/start_navigation", json={
            "waypoints": waypoints,
            "speed_kmh": 20.0
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "started")
        self.assertGreater(data["total_distance_m"], 0)
        self.assertGreater(data["estimated_duration_s"], 0)

        # Status check
        status_resp = self.client.get("/navigation_status")
        status_data = status_resp.get_json()
        self.assertTrue(status_data["active"])
        self.assertFalse(status_data["paused"])
        self.assertEqual(status_data["speed_kmh"], 20.0)

    def test_start_navigation_missing_or_invalid_waypoints_returns_400(self):
        """Validates payload error handling."""
        # Missing waypoints
        res = self.client.post("/start_navigation", json={"speed_kmh": 10.0})
        self.assertEqual(res.status_code, 400)

        # Single point
        res = self.client.post("/start_navigation", json={"waypoints": [[25.0, 121.0]]})
        self.assertEqual(res.status_code, 400)

        # Non-numeric
        res = self.client.post("/start_navigation", json={"waypoints": [["bad", 121.0], [25.0, 121.0]]})
        self.assertEqual(res.status_code, 400)

        # Negative speed
        res = self.client.post("/start_navigation", json={
            "waypoints": [[25.0, 121.0], [25.1, 121.0]],
            "speed_kmh": -5.0
        })
        self.assertEqual(res.status_code, 400)

    def test_pause_and_resume_endpoints(self):
        """POST /pause_navigation and /resume_navigation toggle state correctly."""
        waypoints = [[25.0330, 121.5654], [25.0350, 121.5654]]
        self.client.post("/start_navigation", json={"waypoints": waypoints, "speed_kmh": 10.0})

        # Pause
        res = self.client.post("/pause_navigation")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "paused")

        status = self.client.get("/navigation_status").get_json()
        self.assertTrue(status["paused"])

        # Resume
        res = self.client.post("/resume_navigation")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "resumed")

        status = self.client.get("/navigation_status").get_json()
        self.assertFalse(status["paused"])

    def test_stop_navigation_endpoint(self):
        """POST /stop_navigation halts navigation and returns 200 with current coordinates."""
        waypoints = [[25.0330, 121.5654], [25.0350, 121.5654]]
        self.client.post("/start_navigation", json={"waypoints": waypoints, "speed_kmh": 10.0})

        res = self.client.post("/stop_navigation")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "stopped")
        self.assertIn("current_location", data)
        self.assertIn("lat", data["current_location"])
        self.assertIn("lng", data["current_location"])

        status = self.client.get("/navigation_status").get_json()
        self.assertFalse(status["active"])

    def test_move_step_interrupts_active_navigation(self):
        """Manual WASD steering via /move_step immediately halts active background navigation."""
        waypoints = [[25.0330, 121.5654], [25.0350, 121.5654]]
        self.client.post("/start_navigation", json={"waypoints": waypoints, "speed_kmh": 10.0})
        self.assertTrue(self.test_controller.active)

        # WASD move step
        res = self.client.post("/move_step", json={"direction": "w"})
        self.assertEqual(res.status_code, 200)

        # Navigation controller must now be stopped!
        self.assertFalse(self.test_controller.active)
        status = self.client.get("/navigation_status").get_json()
        self.assertFalse(status["active"])

    def test_update_speed_syncs_with_navigation_controller(self):
        """POST /update_speed updates active navigation speed and returns updated duration."""
        waypoints = [[25.0330, 121.5654], [25.0350, 121.5654]]
        self.client.post("/start_navigation", json={"waypoints": waypoints, "speed_kmh": 10.0})

        res = self.client.post("/update_speed", json={"speed_kmh": 30.0})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "updated")
        self.assertEqual(data["speed_kmh"], 30.0)
        self.assertIn("updated_duration_s", data)

        status = self.client.get("/navigation_status").get_json()
        self.assertEqual(status["speed_kmh"], 30.0)


class TestMapTemplateNavigationHud(unittest.TestCase):
    def setUp(self):
        template_path = Path(main.base_directory) / "src" / "templates" / "map.html"
        if not template_path.is_file():
            template_path = Path(__file__).resolve().parent.parent / "src" / "templates" / "map.html"
        self.content = template_path.read_text(encoding="utf-8")

    def test_navigation_hud_elements_present(self):
        """Map template contains required HUD container and control elements."""
        self.assertIn('id="navigationHud"', self.content)
        self.assertIn('id="navPauseResumeBtn"', self.content)
        self.assertIn('id="navStopBtn"', self.content)
        self.assertIn('id="navHudSpeed"', self.content)
        self.assertIn('id="navHudDistance"', self.content)
        self.assertIn('id="navHudEta"', self.content)
        self.assertIn('id="navStatusBadge"', self.content)

    def test_navigation_hud_js_functions_present(self):
        """Map template defines JavaScript controller and helper functions."""
        self.assertIn("startNavigation", self.content)
        self.assertIn("stopNavigation", self.content)
        self.assertIn("toggleNavPause", self.content)
        self.assertIn("startNavigationStatusPolling", self.content)
        self.assertIn("stopNavigationStatusPolling", self.content)
        self.assertIn("formatNavDistance", self.content)
        self.assertIn("formatNavTime", self.content)

    def test_wasd_interruption_message_present(self):
        """Map template includes interruption toast message."""
        self.assertIn("自動導航已中斷，切換為手動操作", self.content)
        self.assertIn("已到達目的地", self.content)

    def test_format_helpers_via_node(self):
        """Tests JS formatNavDistance and formatNavTime functions using Node.js."""
        js_code = """
        const fs = require('fs');
        const path = process.argv[1];
        const content = fs.readFileSync(path, 'utf8');

        // Extract formatNavDistance and formatNavTime definitions
        eval(content.match(/function formatNavDistance[\\s\\S]*?\\n}/)[0]);
        eval(content.match(/function formatNavTime[\\s\\S]*?\\n}/)[0]);

        const results = {
            distMeters: formatNavDistance(450),
            distKm: formatNavDistance(2500),
            timeSec: formatNavTime(45),
            timeMin: formatNavTime(135),
            timeHour: formatNavTime(3750)
        };
        console.log(JSON.stringify(results));
        """

        template_path = Path(__file__).resolve().parent.parent / "src" / "templates" / "map.html"
        result = subprocess.run(
            ["node", "-e", js_code, str(template_path)],
            capture_output=True,
            text=True,
            check=True
        )

        data = json.loads(result.stdout)
        self.assertEqual(data["distMeters"], "450 m")
        self.assertEqual(data["distKm"], "2.50 km")
        self.assertEqual(data["timeSec"], "45s")
        self.assertEqual(data["timeMin"], "2m 15s")
        self.assertEqual(data["timeHour"], "1h 2m")


if __name__ == "__main__":
    unittest.main()
