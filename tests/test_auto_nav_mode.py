import json
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
from geometry import haversine_distance
from location_sink import MockLocationSink
from navigation_engine import NavigationController


class TestOsrmRoutingMathAndParsing(unittest.TestCase):
    """Test OSRM URL formation, coordinate translation, and fallback routing logic via Node.js."""

    @classmethod
    def setUpClass(cls):
        template_path = Path(__file__).resolve().parent.parent / "src" / "templates" / "map.html"
        cls.html_content = template_path.read_text(encoding="utf-8")

    def _eval_js(self, js_snippet):
        """Helper to evaluate JS snippet with extracted template functions in Node.js."""
        runner_script = f"""
        const fs = require('fs');
        const content = fs.readFileSync(process.argv[1], 'utf-8');

        // Extract functions
        eval(content.match(/function buildOsrmFootRouteUrl[\\s\\S]*?\\n\\}}/)[0]);
        eval(content.match(/function parseOsrmRouteGeometry[\\s\\S]*?\\n\\}}/)[0]);
        eval(content.match(/function getFallbackRoute[\\s\\S]*?\\n\\}}/)[0]);

        {js_snippet}
        """
        template_path = Path(__file__).resolve().parent.parent / "src" / "templates" / "map.html"
        result = subprocess.run(
            ["node", "-e", runner_script, str(template_path)],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)

    def test_osrm_url_formation(self):
        """Verifies OSRM foot routing URL follows https://routing.openstreetmap.de/routed-foot/route/v1/foot/${lng},${lat};${lng},${lat}?overview=full&geometries=geojson."""
        js = """
        const url = buildOsrmFootRouteUrl(25.0330, 121.5654, 25.0400, 121.5750);
        console.log(JSON.stringify({ url: url }));
        """
        data = self._eval_js(js)
        expected_url = (
            "https://routing.openstreetmap.de/routed-foot/route/v1/foot/"
            "121.5654,25.033;121.575,25.04?overview=full&geometries=geojson"
        )
        self.assertEqual(data["url"], expected_url)

    def test_geojson_to_leaflet_coordinate_translation(self):
        """Converts GeoJSON [lng, lat] coordinates to Leaflet/GeoPort [lat, lng]."""
        js = """
        const osrmResponse = {
            code: "Ok",
            routes: [{
                geometry: {
                    type: "LineString",
                    coordinates: [
                        [121.5654, 25.0330],
                        [121.5680, 25.0350],
                        [121.5750, 25.0400]
                    ]
                }
            }]
        };
        const parsed = parseOsrmRouteGeometry(osrmResponse);
        console.log(JSON.stringify({ coords: parsed }));
        """
        data = self._eval_js(js)
        expected_coords = [
            [25.0330, 121.5654],
            [25.0350, 121.5680],
            [25.0400, 121.5750]
        ]
        self.assertEqual(data["coords"], expected_coords)

    def test_parse_osrm_invalid_returns_null(self):
        """Empty, non-Ok, or missing route data returns null."""
        js = """
        const test1 = parseOsrmRouteGeometry(null);
        const test2 = parseOsrmRouteGeometry({ code: "NoRoute", routes: [] });
        const test3 = parseOsrmRouteGeometry({ code: "Ok", routes: [{ geometry: { coordinates: [] } }] });
        const test4 = parseOsrmRouteGeometry({});
        console.log(JSON.stringify({ t1: test1, t2: test2, t3: test3, t4: test4 }));
        """
        data = self._eval_js(js)
        self.assertIsNone(data["t1"])
        self.assertIsNone(data["t2"])
        self.assertIsNone(data["t3"])
        self.assertIsNone(data["t4"])

    def test_fallback_route_generation(self):
        """Fallback direct straight-line route produces 2-point array with start and destination."""
        js = """
        const fallback = getFallbackRoute(25.0330, 121.5654, 25.0400, 121.5750);
        console.log(JSON.stringify({ fallback: fallback }));
        """
        data = self._eval_js(js)
        expected_fallback = [
            [25.0330, 121.5654],
            [25.0400, 121.5750]
        ]
        self.assertEqual(data["fallback"], expected_fallback)

    def test_osrm_route_caching_in_memory(self):
        """fetchOsrmRoute caches successful route geometry keyed by 5-decimal coordinates."""
        runner_script = """
        const fs = require('fs');
        const content = fs.readFileSync(process.argv[1], 'utf-8');

        global.window = global;
        eval(content.match(/function buildOsrmFootRouteUrl[\\s\\S]*?\\n\\}/)[0]);
        eval(content.match(/function parseOsrmRouteGeometry[\\s\\S]*?\\n\\}/)[0]);
        eval(content.match(/function getFallbackRoute[\\s\\S]*?\\n\\}/)[0]);
        eval(content.match(/const osrmRouteCache = new Map\\(\\);\\s*window\\.osrmRouteCache = osrmRouteCache;/)[0]);
        eval(content.match(/async function fetchOsrmRoute[\\s\\S]*?\\n\\}/)[0]);

        (async () => {
            let fetchCount = 0;
            global.fetch = async function() {
                fetchCount++;
                return {
                    ok: true,
                    json: async () => ({
                        code: "Ok",
                        routes: [{
                            geometry: {
                                coordinates: [
                                    [121.5654, 25.0330],
                                    [121.5750, 25.0400]
                                ]
                            }
                        }]
                    })
                };
            };

            const r1 = await fetchOsrmRoute(25.033001, 121.565401, 25.040001, 121.575001);
            const r2 = await fetchOsrmRoute(25.033002, 121.565402, 25.040002, 121.575002);

            const cacheKey = "25.03300,121.56540-25.04000,121.57500";
            const inCache = osrmRouteCache.has(cacheKey);

            console.log(JSON.stringify({
                fetchCount: fetchCount,
                inCache: inCache,
                r1Count: r1.length,
                r2Count: r2.length
            }));
        })();
        """
        template_path = Path(__file__).resolve().parent.parent / "src" / "templates" / "map.html"
        result = subprocess.run(
            ["node", "-e", runner_script, str(template_path)],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["fetchCount"], 1)
        self.assertTrue(data["inCache"])
        self.assertEqual(data["r1Count"], 2)
        self.assertEqual(data["r2Count"], 2)

    def test_map_template_smooth_marker_animation_css(self):
        """Map template contains CSS transition for smooth marker icon animation."""
        self.assertIn(".leaflet-marker-icon", self.html_content)
        self.assertIn("transition: transform", self.html_content)

    def test_perform_move_step_uses_get_coordinates(self):
        """performMoveStep reuses getCoordinates instead of duplicate parsing."""
        self.assertIn("coords = getCoordinates()", self.html_content)


class TestCameraLockAndStateToggling(unittest.TestCase):
    """Test camera lock state toggling and auto-nav toggle behavior via Node.js."""

    def _eval_state_js(self, js_snippet):
        runner_script = f"""
        const fs = require('fs');
        const content = fs.readFileSync(process.argv[1], 'utf-8');

        // Mock browser DOM & window environment
        global.window = global;
        global.document = {{
            getElementById: function(id) {{
                return {{
                    classList: {{
                        add: function(cls) {{}},
                        remove: function(cls) {{}}
                    }},
                    style: {{ cursor: '' }},
                    title: ''
                }};
            }}
        }};
        global.displayToast = function(msg) {{}};
        global.marker = null;

        // Extract state variables and toggle functions
        eval(content.match(/window\\.isAutoNavMode\\s*=\\s*false;/)[0]);
        eval(content.match(/window\\.isCameraLocked\\s*=\\s*true;/)[0]);
        eval(content.match(/function toggleAutoNavMode[\\s\\S]*?\\n\\}}/)[0]);
        eval(content.match(/function setCameraLock[\\s\\S]*?\\n\\}}/)[0]);
        eval(content.match(/function toggleCameraLock[\\s\\S]*?\\n\\}}/)[0]);
        eval(content.match(/function getCoordinates[\\s\\S]*?\\n\\}}/)[0]);

        {js_snippet}
        """
        template_path = Path(__file__).resolve().parent.parent / "src" / "templates" / "map.html"
        result = subprocess.run(
            ["node", "-e", runner_script, str(template_path)],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)

    def test_camera_lock_initial_and_toggling(self):
        """Camera lock starts locked (true), toggles to unlocked (false), and back to locked."""
        js = """
        const initial = window.isCameraLocked;
        const afterFirstToggle = toggleCameraLock();
        const afterSecondToggle = toggleCameraLock();
        console.log(JSON.stringify({
            initial: initial,
            first: afterFirstToggle,
            second: afterSecondToggle
        }));
        """
        data = self._eval_state_js(js)
        self.assertTrue(data["initial"])
        self.assertFalse(data["first"])
        self.assertTrue(data["second"])

    def test_set_camera_lock_explicit(self):
        """setCameraLock sets camera lock state explicitly."""
        js = """
        setCameraLock(false);
        const unlocked = window.isCameraLocked;
        setCameraLock(true);
        const locked = window.isCameraLocked;
        console.log(JSON.stringify({ unlocked: unlocked, locked: locked }));
        """
        data = self._eval_state_js(js)
        self.assertFalse(data["unlocked"])
        self.assertTrue(data["locked"])

    def test_auto_nav_mode_toggling(self):
        """Auto nav mode starts false, toggles to true, and back to false."""
        js = """
        const initial = window.isAutoNavMode;
        const firstToggle = toggleAutoNavMode();
        const secondToggle = toggleAutoNavMode();
        toggleAutoNavMode(true);
        const explicitTrue = window.isAutoNavMode;
        toggleAutoNavMode(false);
        const explicitFalse = window.isAutoNavMode;
        console.log(JSON.stringify({
            initial: initial,
            first: firstToggle,
            second: secondToggle,
            explicitTrue: explicitTrue,
            explicitFalse: explicitFalse
        }));
        """
        data = self._eval_state_js(js)
        self.assertFalse(data["initial"])
        self.assertTrue(data["first"])
        self.assertFalse(data["second"])
        self.assertTrue(data["explicitTrue"])
        self.assertFalse(data["explicitFalse"])


class TestMapTemplateAutoNavVerification(unittest.TestCase):
    """Verify HTML template contains required Auto Nav controls, handlers, and elements."""

    @classmethod
    def setUpClass(cls):
        template_path = Path(__file__).resolve().parent.parent / "src" / "templates" / "map.html"
        cls.content = template_path.read_text(encoding="utf-8")

    def test_auto_nav_button_elements_present(self):
        """Template contains Auto Navigation EasyButton and icon."""
        self.assertIn("autoNavButton", self.content)
        self.assertIn("Auto Navigation", self.content)
        self.assertIn("lni-direction-alt", self.content)

    def test_camera_follow_button_elements_present(self):
        """Template contains Camera Follow button with ID cameraFollowButton and icon."""
        self.assertIn("cameraFollowButton", self.content)
        self.assertIn("lni-target", self.content)

    def test_auto_nav_toast_notifications_present(self):
        """Template contains indicator toasts for mode toggle and arrival."""
        self.assertIn("自動導航模式已開啟：請點擊地圖目的地出發", self.content)
        self.assertIn("自動導航模式已關閉", self.content)
        self.assertIn("已到達目的地", self.content)

    def test_osrm_url_and_fallback_functions_present(self):
        """Template defines OSRM foot routing URL generator and fallback logic."""
        self.assertIn("buildOsrmFootRouteUrl", self.content)
        self.assertIn("routing.openstreetmap.de/routed-foot/route/v1/foot/", self.content)
        self.assertIn("overview=full&geometries=geojson", self.content)
        self.assertIn("parseOsrmRouteGeometry", self.content)
        self.assertIn("getFallbackRoute", self.content)
        self.assertIn("fetchOsrmRoute", self.content)

    def test_camera_auto_centering_in_update_position(self):
        """Template performs camera auto-centering (map.panTo) in updatePositionOnStep when camera is locked."""
        self.assertIn("map.panTo([lat, lng])", self.content)
        self.assertIn("window.isCameraLocked", self.content)

    def test_route_cleanup_functions_present(self):
        """Template defines clearNavRoute and cleans up route polyline upon completion and stopping."""
        self.assertIn("function clearNavRoute", self.content)
        self.assertIn("clearNavRoute()", self.content)
        self.assertIn("window.navRoutePolyline", self.content)


class TestAutoNavLifecycleIntegration(unittest.TestCase):
    """End-to-end integration tests validating navigation lifecycle with mock location sink."""

    def setUp(self):
        self.app = main.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.mock_sink = MockLocationSink()
        main.set_location_sink(self.mock_sink)
        main.set_current_speed(5.0)

    def tearDown(self):
        if hasattr(self.app, "navigation_controller"):
            self.app.navigation_controller.stop()
            delattr(self.app, "navigation_controller")
        main.set_current_speed(5.0)

    def test_start_navigation_with_waypoints_and_polling(self):
        """Full lifecycle: start navigation, poll status, and verify active worker."""
        # Start at Taipei 101
        main.location = "25.0330 121.5654"
        self.mock_sink.set_location(25.0330, 121.5654)

        waypoints = [
            [25.0330, 121.5654],
            [25.0335, 121.5654],
            [25.0340, 121.5654]
        ]

        # 1. Start navigation
        start_res = self.client.post("/start_navigation", json={
            "waypoints": waypoints,
            "speed_kmh": 20.0
        })
        self.assertEqual(start_res.status_code, 200)
        start_data = start_res.get_json()
        self.assertEqual(start_data.get("status"), "started")
        self.assertGreater(start_data.get("total_distance_m"), 0)

        # 2. Query status
        status_res = self.client.get("/navigation_status")
        self.assertEqual(status_res.status_code, 200)
        status_data = status_res.get_json()
        self.assertTrue(status_data["active"])
        self.assertFalse(status_data["paused"])
        self.assertFalse(status_data["completed"])
        self.assertEqual(status_data["speed_kmh"], 20.0)

        # 3. Stop navigation
        stop_res = self.client.post("/stop_navigation")
        self.assertEqual(stop_res.status_code, 200)
        stop_data = stop_res.get_json()
        self.assertEqual(stop_data.get("status"), "stopped")

        # Status after stop
        post_stop = self.client.get("/navigation_status").get_json()
        self.assertFalse(post_stop["active"])

    def test_navigation_runs_to_completion(self):
        """Controller steps through waypoints until completed state is reached."""
        start_pt = (25.0330, 121.5654)
        end_pt = (25.0332, 121.5654)  # ~22.2 meters away

        waypoints = [start_pt, end_pt]
        total_dist = haversine_distance(start_pt[0], start_pt[1], end_pt[0], end_pt[1])

        # Step at 100 km/h (~27.7 m/s) -> completes in 1 step
        controller = NavigationController(
            sink=self.mock_sink,
            tick_interval=0.01
        )
        self.app.navigation_controller = controller
        controller.start(waypoints, speed_kmh=100.0)

        # Wait for worker to finish (very short trip)
        for _ in range(50):
            time.sleep(0.05)
            status = controller.get_status()
            if status["completed"]:
                break

        final_status = controller.get_status()
        self.assertTrue(final_status["completed"])
        self.assertFalse(final_status["active"])
        self.assertAlmostEqual(final_status["remaining_distance_m"], 0.0, places=1)

        # Device location should be at destination point
        sink_loc = self.mock_sink.last_location
        self.assertIsNotNone(sink_loc)
        self.assertAlmostEqual(sink_loc[0], end_pt[0], places=4)
        self.assertAlmostEqual(sink_loc[1], end_pt[1], places=4)


if __name__ == "__main__":
    unittest.main()
