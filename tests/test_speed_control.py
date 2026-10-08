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
from geometry import validate_speed
from location_sink import MockLocationSink


class TestUpdateSpeedEndpoint(unittest.TestCase):
    def setUp(self):
        self.app = main.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.mock_sink = MockLocationSink()
        main.set_location_sink(self.mock_sink)
        main.set_current_speed(5.0)

    def tearDown(self):
        if hasattr(self.app, "navigation_controller"):
            delattr(self.app, "navigation_controller")
        main.set_current_speed(5.0)

    def test_update_speed_valid_float(self):
        """Valid positive float speed updates state and returns 200 with status."""
        response = self.client.post("/update_speed", json={"speed_kmh": 20.0})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("status"), "updated")
        self.assertEqual(data.get("speed_kmh"), 20.0)
        self.assertEqual(main.get_current_speed(), 20.0)

    def test_update_speed_valid_int(self):
        """Integer speed (e.g. 60) is accepted and converted to float."""
        response = self.client.post("/update_speed", json={"speed_kmh": 60})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("status"), "updated")
        self.assertEqual(data.get("speed_kmh"), 60.0)
        self.assertEqual(main.get_current_speed(), 60.0)

    def test_update_speed_valid_numeric_string(self):
        """Numeric string representation (e.g. '15.5') is parsed correctly."""
        response = self.client.post("/update_speed", json={"speed_kmh": "15.5"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("status"), "updated")
        self.assertEqual(data.get("speed_kmh"), 15.5)
        self.assertEqual(main.get_current_speed(), 15.5)

    def test_update_speed_contract_when_navigation_inactive(self):
        """POST /update_speed always returns updated_duration_s even when navigation is not active."""
        response = self.client.post("/update_speed", json={"speed_kmh": 25.0})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("speed_kmh"), 25.0)
        self.assertIn("updated_duration_s", data)
        self.assertEqual(data.get("updated_duration_s"), 0.0)

    def test_update_speed_zero_returns_400(self):
        """Speed of 0 is invalid and returns 400 error."""
        response = self.client.post("/update_speed", json={"speed_kmh": 0})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_update_speed_negative_returns_400(self):
        """Negative speed returns 400 error."""
        response = self.client.post("/update_speed", json={"speed_kmh": -10.0})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_update_speed_non_numeric_returns_400(self):
        """Non-numeric speed value returns 400 error."""
        response = self.client.post("/update_speed", json={"speed_kmh": "invalid_speed"})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_update_speed_missing_speed_param_returns_400(self):
        """Request missing 'speed_kmh' key returns 400 error."""
        response = self.client.post("/update_speed", json={"other_key": 20.0})
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_update_speed_non_json_returns_400(self):
        """Non-JSON payload or invalid body returns 400 error."""
        response = self.client.post(
            "/update_speed",
            data="not-json",
            content_type="text/plain"
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_update_speed_empty_body_returns_400(self):
        """Empty request body returns 400 error."""
        response = self.client.post("/update_speed", data="")
        self.assertEqual(response.status_code, 400)

    def test_update_speed_syncs_with_navigation_controller(self):
        """When an active navigation controller exists, updating speed notifies it."""
        class MockNavController:
            def __init__(self):
                self.speed_kmh = 5.0
                self.updated_speeds = []

            def update_speed(self, speed):
                self.speed_kmh = speed
                self.updated_speeds.append(speed)

        controller = MockNavController()
        self.app.navigation_controller = controller

        response = self.client.post("/update_speed", json={"speed_kmh": 35.0})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(controller.speed_kmh, 35.0)
        self.assertEqual(controller.updated_speeds, [35.0])
        self.assertEqual(main.get_current_speed(), 35.0)


class TestMoveStepFallbackSpeed(unittest.TestCase):
    def setUp(self):
        self.app = main.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.mock_sink = MockLocationSink()
        main.set_location_sink(self.mock_sink)
        main.set_current_speed(5.0)

    def tearDown(self):
        if hasattr(self.app, "navigation_controller"):
            delattr(self.app, "navigation_controller")
        main.set_current_speed(5.0)

    def test_move_step_uses_updated_speed_when_not_specified(self):
        """When speed_kmh is omitted in /move_step, it uses the active backend speed."""
        main.location = "25.0330 121.5654"

        # Update speed to 20 km/h (Bike)
        res_speed = self.client.post("/update_speed", json={"speed_kmh": 20.0})
        self.assertEqual(res_speed.status_code, 200)

        # Call move_step without speed_kmh
        response = self.client.post("/move_step", json={"direction": "w"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        # Step distance should reflect 20 km/h (20 / 3.6 m)
        expected_distance = 20.0 / 3.6
        self.assertAlmostEqual(data["distance_m"], expected_distance, places=4)

    def test_move_step_uses_default_speed_initially(self):
        """Initial move_step without speed_kmh defaults to initial backend speed (5 km/h)."""
        main.location = "25.0330 121.5654"
        response = self.client.post("/move_step", json={"direction": "d"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        expected_distance = 5.0 / 3.6
        self.assertAlmostEqual(data["distance_m"], expected_distance, places=4)

    def test_move_step_dynamic_speed_transitions(self):
        """Successive steps dynamically adapt to new speeds set via /update_speed."""
        main.location = "25.0330 121.5654"

        # Switch to Drive: 60 km/h
        self.client.post("/update_speed", json={"speed_kmh": 60.0})
        res1 = self.client.post("/move_step", json={"direction": "w"})
        self.assertEqual(res1.status_code, 200)
        self.assertAlmostEqual(res1.get_json()["distance_m"], 60.0 / 3.6, places=4)

        # Switch to Walk: 5 km/h
        self.client.post("/update_speed", json={"speed_kmh": 5.0})
        res2 = self.client.post("/move_step", json={"direction": "w"})
        self.assertEqual(res2.status_code, 200)
        self.assertAlmostEqual(res2.get_json()["distance_m"], 5.0 / 3.6, places=4)

    def test_explicit_speed_overrides_backend_speed_without_altering_it(self):
        """Passing explicit speed_kmh in /move_step uses that speed for the single step."""
        main.location = "25.0330 121.5654"
        main.set_current_speed(60.0)

        # Explicit speed 10 km/h
        res1 = self.client.post("/move_step", json={"direction": "w", "speed_kmh": 10.0})
        self.assertEqual(res1.status_code, 200)
        self.assertAlmostEqual(res1.get_json()["distance_m"], 10.0 / 3.6, places=4)

        # Next step without speed falls back to 60.0
        res2 = self.client.post("/move_step", json={"direction": "w"})
        self.assertEqual(res2.status_code, 200)
        self.assertAlmostEqual(res2.get_json()["distance_m"], 60.0 / 3.6, places=4)


class TestMapTemplateSpeedControl(unittest.TestCase):
    def setUp(self):
        template_path = Path(main.base_directory) / "src" / "templates" / "map.html"
        if not template_path.is_file():
            template_path = Path(__file__).resolve().parent.parent / "src" / "templates" / "map.html"
        self.content = template_path.read_text(encoding="utf-8")

    def test_speed_control_html_elements_present(self):
        """Map template contains number input, range slider, and preset buttons."""
        self.assertIn("speedNumberInput", self.content)
        self.assertIn("speedRangeSlider", self.content)
        self.assertIn("speedPresetWalk", self.content)
        self.assertIn("speedPresetBike", self.content)
        self.assertIn("speedPresetDrive", self.content)

        # Verify preset texts Walk (5 km/h), Bike (20 km/h), Drive (60 km/h)
        self.assertIn("Walk (5 km/h)", self.content)
        self.assertIn("Bike (20 km/h)", self.content)
        self.assertIn("Drive (60 km/h)", self.content)

    def test_speed_persistence_and_backend_sync_present(self):
        """Map template contains localStorage persistence and /update_speed endpoint call."""
        self.assertIn("geoport_speed_kmh", self.content)
        self.assertIn("localStorage.setItem('geoport_speed_kmh'", self.content)
        self.assertIn("localStorage.getItem('geoport_speed_kmh'", self.content)
        self.assertIn("/update_speed", self.content)
        self.assertIn("window.currentSpeedKmh", self.content)
        self.assertIn("setSpeed", self.content)
        self.assertIn("syncSpeedControls", self.content)

    def test_fixed_calculate_time_function_present(self):
        """calculateTime function parses numeric speeds and supports presets without falling back to 6 km/h."""
        self.assertIn("function calculateTime", self.content)
        self.assertIn("speedPresets", self.content)
        self.assertIn("typeof velocity === 'number'", self.content)
        self.assertIn("parseFloat", self.content)


class TestCalculateTimeLogic(unittest.TestCase):
    def test_calculate_time_with_node(self):
        """Run Node.js to evaluate calculateTime across diverse numeric and string inputs."""
        js_code = """
        const fs = require('fs');
        const path = require('path');
        const html = fs.readFileSync(process.argv[1], 'utf-8');

        // Extract calculateTime function definition
        const match = html.match(/function calculateTime\\([\\s\\S]*?\\)\\s*\\{[\\s\\S]*?\\n\\}/);
        if (!match) {
            console.error('calculateTime not found');
            process.exit(1);
        }

        eval(match[0]);

        const results = {
            num30: calculateTime(30, 30),
            str30: calculateTime(30, "30"),
            walk: calculateTime(6, "walk"),
            run: calculateTime(12, "run"),
            ride: calculateTime(20, "ride"),
            drive: calculateTime(50, "drive"),
            fallbackInvalid: calculateTime(6, "unknown"),
            fallbackZero: calculateTime(6, 0),
            fallbackNegative: calculateTime(6, -10),
            fallbackNull: calculateTime(6, null)
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
        # 30 km at 30 km/h = 1 hour = 3600 seconds
        self.assertAlmostEqual(data["num30"], 3600.0)
        self.assertAlmostEqual(data["str30"], 3600.0)
        # Walk is 6 km/h: 6 km at 6 km/h = 3600 seconds
        self.assertAlmostEqual(data["walk"], 3600.0)
        # Run is 12 km/h: 12 km at 12 km/h = 3600 seconds
        self.assertAlmostEqual(data["run"], 3600.0)
        # Ride is 20 km/h: 20 km at 20 km/h = 3600 seconds
        self.assertAlmostEqual(data["ride"], 3600.0)
        # Drive is 50 km/h: 50 km at 50 km/h = 3600 seconds
        self.assertAlmostEqual(data["drive"], 3600.0)
        # Fallbacks all fall back to walk (6 km/h): 6 km at 6 km/h = 3600 seconds
        self.assertAlmostEqual(data["fallbackInvalid"], 3600.0)
        self.assertAlmostEqual(data["fallbackZero"], 3600.0)
        self.assertAlmostEqual(data["fallbackNegative"], 3600.0)
        self.assertAlmostEqual(data["fallbackNull"], 3600.0)


class TestSpeedValidation(unittest.TestCase):
    def test_valid_speeds(self):
        self.assertEqual(validate_speed(5), 5.0)
        self.assertEqual(validate_speed(20.5), 20.5)
        self.assertEqual(validate_speed("15.2"), 15.2)

    def test_invalid_speeds_raise_value_error(self):
        with self.assertRaises(ValueError):
            validate_speed(0)
        with self.assertRaises(ValueError):
            validate_speed(-10)
        with self.assertRaises(ValueError):
            validate_speed("abc")
        with self.assertRaises(ValueError):
            validate_speed(float("nan"))
        with self.assertRaises(ValueError):
            validate_speed(float("inf"))
        with self.assertRaises(ValueError):
            validate_speed(None)


if __name__ == "__main__":
    unittest.main()
