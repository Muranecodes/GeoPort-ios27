import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

# Ensure src is in python path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import main
from geometry import haversine_distance
from location_sink import MockLocationSink


class TestKeyboardSteering(unittest.TestCase):
    def setUp(self):
        self.app = main.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.mock_sink = MockLocationSink()
        main.set_location_sink(self.mock_sink)

    def tearDown(self):
        if hasattr(self.app, "navigation_controller"):
            delattr(self.app, "navigation_controller")

    def test_rapid_sequential_move_step_north(self):
        """Simulate holding 'W' (North) for 5 consecutive 1-second intervals at 5 km/h."""
        start_lat = 25.0330
        start_lng = 121.5654
        main.location = f"{start_lat} {start_lng}"
        speed_kmh = 5.0
        expected_step_m = speed_kmh / 3.6  # ~1.38889 meters per second

        prev_lat = start_lat
        prev_lng = start_lng

        for i in range(5):
            response = self.client.post("/move_step", json={
                "direction": "w",
                "speed_kmh": speed_kmh
            })
            self.assertEqual(response.status_code, 200)
            data = response.get_json()

            # Lat should increase monotonically (moving North)
            self.assertGreater(data["lat"], prev_lat)
            # Lng should remain approximately identical
            self.assertAlmostEqual(data["lng"], prev_lng, places=5)
            # Step distance should be deterministic
            self.assertAlmostEqual(data["distance_m"], expected_step_m, places=4)

            # Check sink received this coordinate
            self.assertEqual(len(self.mock_sink.locations), i + 1)
            self.assertEqual(self.mock_sink.last_location, (data["lat"], data["lng"]))

            # Verify server global location updated
            self.assertEqual(main.location, f"{data['lat']} {data['lng']}")

            prev_lat = data["lat"]
            prev_lng = data["lng"]

        # Total distance from origin should be 5 * step_dist
        total_dist = haversine_distance(start_lat, start_lng, prev_lat, prev_lng)
        self.assertAlmostEqual(total_dist, 5 * expected_step_m, places=3)

    def test_rapid_direction_switching_w_d_s_a(self):
        """Simulate steering switching directions: W -> D -> S -> A (box path)."""
        start_lat = 25.0330
        start_lng = 121.5654
        main.location = f"{start_lat} {start_lng}"
        speed_kmh = 10.0  # ~2.7778 m/s
        steps_per_leg = 3

        # Leg 1: Steer North ('w')
        for _ in range(steps_per_leg):
            res = self.client.post("/move_step", json={"direction": "w", "speed_kmh": speed_kmh})
            self.assertEqual(res.status_code, 200)
        north_lat, north_lng = map(float, main.location.split())
        self.assertGreater(north_lat, start_lat)
        self.assertAlmostEqual(north_lng, start_lng, places=5)

        # Leg 2: Switch to East ('d')
        for _ in range(steps_per_leg):
            res = self.client.post("/move_step", json={"direction": "d", "speed_kmh": speed_kmh})
            self.assertEqual(res.status_code, 200)
        east_lat, east_lng = map(float, main.location.split())
        self.assertAlmostEqual(east_lat, north_lat, places=5)
        self.assertGreater(east_lng, north_lng)

        # Leg 3: Switch to South ('s')
        for _ in range(steps_per_leg):
            res = self.client.post("/move_step", json={"direction": "s", "speed_kmh": speed_kmh})
            self.assertEqual(res.status_code, 200)
        south_lat, south_lng = map(float, main.location.split())
        self.assertLess(south_lat, east_lat)
        self.assertAlmostEqual(south_lng, east_lng, places=5)

        # Leg 4: Switch to West ('a')
        for _ in range(steps_per_leg):
            res = self.client.post("/move_step", json={"direction": "a", "speed_kmh": speed_kmh})
            self.assertEqual(res.status_code, 200)
        final_lat, final_lng = map(float, main.location.split())
        self.assertAlmostEqual(final_lat, south_lat, places=5)
        self.assertLess(final_lng, south_lng)

        # Completed a closed loop: final coords should be within ~0.5m of start
        loop_error_m = haversine_distance(start_lat, start_lng, final_lat, final_lng)
        self.assertLess(loop_error_m, 0.5)

        # Sink should have captured all 12 dispatches in sequential order
        self.assertEqual(len(self.mock_sink.locations), 12)

    def test_dynamic_speed_changes_during_steering(self):
        """Simulate dynamic speed adjustments (5 km/h -> 20 km/h -> 60 km/h) across steps."""
        start_lat = 25.0330
        start_lng = 121.5654
        main.location = f"{start_lat} {start_lng}"

        # Step 1: Walking 5 km/h
        res1 = self.client.post("/move_step", json={"direction": "d", "speed_kmh": 5.0})
        self.assertEqual(res1.status_code, 200)
        d1 = res1.get_json()["distance_m"]
        self.assertAlmostEqual(d1, 5.0 / 3.6, places=4)

        # Step 2: Cycling 20 km/h
        res2 = self.client.post("/move_step", json={"direction": "d", "speed_kmh": 20.0})
        self.assertEqual(res2.status_code, 200)
        d2 = res2.get_json()["distance_m"]
        self.assertAlmostEqual(d2, 20.0 / 3.6, places=4)

        # Step 3: Driving 60 km/h
        res3 = self.client.post("/move_step", json={"direction": "d", "speed_kmh": 60.0})
        self.assertEqual(res3.status_code, 200)
        d3 = res3.get_json()["distance_m"]
        self.assertAlmostEqual(d3, 60.0 / 3.6, places=4)

        self.assertGreater(d3, d2)
        self.assertGreater(d2, d1)

    def test_case_insensitive_direction_inputs(self):
        """Verify directions accept upper and lower case letters."""
        main.location = "25.0330 121.5654"
        for dir_key in ["w", "W", "a", "A", "s", "S", "d", "D"]:
            res = self.client.post("/move_step", json={"direction": dir_key, "speed_kmh": 5.0})
            self.assertEqual(res.status_code, 200)

    def test_keyboard_step_cancels_active_navigation(self):
        """Verify that any keyboard /move_step immediately interrupts active navigation."""
        class MockNavigationController:
            def __init__(self):
                self.stopped = False
            def stop(self):
                self.stopped = True

        controller = MockNavigationController()
        self.app.navigation_controller = controller
        main.location = "25.0330 121.5654"

        res = self.client.post("/move_step", json={"direction": "w", "speed_kmh": 5.0})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(controller.stopped)

    def test_map_html_contains_keyboard_steering_implementation(self):
        """Verify that map.html contains required functions, event listeners, and contracts."""
        template_path = Path(main.base_directory) / "src" / "templates" / "map.html"
        if not template_path.is_file():
            template_path = Path(__file__).resolve().parent.parent / "src" / "templates" / "map.html"

        content = template_path.read_text(encoding="utf-8")

        # 1. Key listeners on window
        self.assertIn("window.addEventListener('keydown', handleKeyDown)", content)
        self.assertIn("window.addEventListener('keyup', handleKeyUp)", content)

        # 2. Key mapping supports WASD and Arrow keys
        self.assertIn("KeyW", content)
        self.assertIn("ArrowUp", content)
        self.assertIn("KeyA", content)
        self.assertIn("ArrowLeft", content)
        self.assertIn("KeyS", content)
        self.assertIn("ArrowDown", content)
        self.assertIn("KeyD", content)
        self.assertIn("ArrowRight", content)

        # 3. Interactive element protection
        self.assertIn("isInteractiveElement", content)
        self.assertIn("INPUT", content)
        self.assertIn("TEXTAREA", content)
        self.assertIn("SELECT", content)
        self.assertIn("isContentEditable", content)

        # 4. 1-second interval ticker and /move_step endpoint call
        self.assertIn("1000", content)
        self.assertIn("/move_step", content)

        # 5. Speed helper with default
        self.assertIn("getCurrentSpeed", content)
        self.assertIn("return 5.0", content)

    def test_wasd_interruption_clears_nav_route(self):
        """When keyboard WASD interrupts active navigation, clearNavRoute is invoked."""
        js_code = """
        const fs = require('fs');
        const content = fs.readFileSync(process.argv[1], 'utf-8');

        global.window = global;
        global.document = {
            activeElement: null,
            getElementById: function() { return null; }
        };
        global.isNavigating = true;
        global.navPollInterval = 123;
        global.pressedKeyDirections = new Map();
        global.activeMovementInterval = null;
        global.activeDirection = null;
        global.displayToast = function() {};

        let cleared = false;
        global.clearNavRoute = function() {
            cleared = true;
        };
        global.stopNavigationStatusPolling = function() {
            global.isNavigating = false;
            global.navPollInterval = null;
        };
        global.performMoveStep = function() {};

        eval(content.match(/function isInteractiveElement[\\s\\S]*?\\n\\}/)[0]);
        eval(content.match(/function getDirectionFromEvent[\\s\\S]*?\\n\\}/)[0]);
        eval(content.match(/function handleKeyDown[\\s\\S]*?\\n\\}/)[0]);

        handleKeyDown({
            code: 'KeyW',
            key: 'w',
            preventDefault: function() {}
        });

        if (global.activeMovementInterval) {
            clearInterval(global.activeMovementInterval);
        }

        console.log(JSON.stringify({ cleared: cleared, isNavigating: global.isNavigating }));
        """
        template_path = Path(__file__).resolve().parent.parent / "src" / "templates" / "map.html"
        result = subprocess.run(
            ["node", "-e", js_code, str(template_path)],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        self.assertTrue(data["cleared"])
        self.assertFalse(data["isNavigating"])

    def test_keyboard_anti_burst_timeout_and_pacing(self):
        """Verify map.html implements anti-burst timing with activeMovementTimeout and lastMoveStepTime."""
        template_path = Path(__file__).resolve().parent.parent / "src" / "templates" / "map.html"
        content = template_path.read_text(encoding="utf-8")
        self.assertIn("activeMovementTimeout", content)
        self.assertIn("lastMoveStepTime", content)
        self.assertIn("elapsed >= 950", content)
        self.assertIn("Math.max(50, 1000 - elapsed)", content)
        self.assertIn("stopKeyboardSteering", content)


if __name__ == "__main__":
    unittest.main()
