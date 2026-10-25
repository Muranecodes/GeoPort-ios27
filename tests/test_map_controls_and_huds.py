import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

# Ensure src is in python path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import main


class TestMapControlsAndHuds(unittest.TestCase):
    """Ticket 02 test suite: CartoDB Voyager default, decluttered toolbar pill buttons, and blossom HUD styling."""

    def setUp(self):
        self.app = main.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

        self.template_path = Path(__file__).resolve().parent.parent / "src" / "templates" / "map.html"
        self.content = self.template_path.read_text(encoding="utf-8")

    def test_default_tile_layer_is_free_openstreetmap(self):
        """openStreetMapTileLayer.addTo(map) is executed as the default initial tile layer on startup (100% free, no API key)."""
        # openStreetMapTileLayer must be added to map on startup
        self.assertIn("openStreetMapTileLayer.addTo(map);", self.content)
        # stadiaTileLayer must NOT be added to map as default
        self.assertNotIn("stadiaTileLayer.addTo(map);", self.content)

        # Layer switcher baseLayers dictionary must still include base layers
        self.assertIn('"OpenStreetMap": openStreetMapTileLayer', self.content)
        self.assertIn('"Esri World Street Map": Esri_WorldStreetMap', self.content)

    def test_auto_nav_route_polyline_styling(self):
        """Auto Navigation route polyline is styled with #6B9E78, rounded join and cap."""
        # Color must be soft botanical sage green
        self.assertIn("#6B9E78", self.content)

        # In handleAutoNavMapClick, polyline options must specify #6B9E78, weight 6, opacity 0.88, lineCap and lineJoin round
        polyline_match = re.search(r"window\.navRoutePolyline\s*=\s*L\.polyline\([^,]+,\s*\{([^}]+)\}\)", self.content)
        self.assertIsNotNone(polyline_match, "window.navRoutePolyline initialization options must be present")
        options_str = polyline_match.group(1)
        self.assertIn("#6B9E78", options_str)
        self.assertIn("6", options_str)
        self.assertIn("0.88", options_str)
        self.assertIn("lineCap", options_str)
        self.assertIn("lineJoin", options_str)
        self.assertIn("'round'", options_str)

    def test_css_hides_unused_filelayer_controls(self):
        """CSS rule hides unused controls in .leaflet-control-filelayer with display: none !important."""
        # Must have rule in style hiding unused filelayer controls
        self.assertTrue(
            re.search(r"\.leaflet-control-filelayer\s*>\s*\*:not\(#autoNavButton\):not\(#cameraFollowButton\)[^{]*\{[^}]*display:\s*none\s*!important", self.content) or
            re.search(r"\.leaflet-control-filelayer[^{]*styles-menu[^{]*display:\s*none\s*!important", self.content),
            "CSS rule must hide unused controls in .leaflet-control-filelayer while keeping #autoNavButton and #cameraFollowButton visible"
        )
        self.assertIn("#styles-menu", self.content)

    def test_autonav_and_camera_follow_buttons_markup_and_pill_styling(self):
        """#autoNavButton and #cameraFollowButton have required icon classes, Chinese labels, and pill styling."""
        # Icons and Chinese text in button markup / easyButton states
        self.assertIn("lni-direction-alt", self.content)
        self.assertIn("自動導航", self.content)
        self.assertIn("lni-target", self.content)
        self.assertIn("鏡頭跟隨", self.content)

        # Style rule for pill buttons
        self.assertTrue(
            re.search(r"#autoNavButton[^{]*\{[^}]*border-radius:\s*(?:999px|20px)", self.content) or
            re.search(r"#cameraFollowButton[^{]*\{[^}]*border-radius:\s*(?:999px|20px)", self.content),
            "#autoNavButton and #cameraFollowButton must have rounded pill border-radius"
        )

    def test_speed_control_and_hud_rounded_card_styling(self):
        """Floating speed widget and navigation HUD are styled with rounded card styling (border-radius: 20px)."""
        # .speed-control-widget styling
        self.assertTrue(
            re.search(r"\.speed-control-widget\s*\{[^}]*border-radius:\s*20px", self.content),
            ".speed-control-widget must have border-radius: 20px"
        )
        # .navigation-hud styling
        self.assertTrue(
            re.search(r"\.navigation-hud\s*\{[^}]*border-radius:\s*20px", self.content),
            ".navigation-hud must have border-radius: 20px"
        )

    def test_sync_speed_controls_planting_mode_toggled_via_node(self):
        """In syncSpeedControls, selecting 19.1 km/h toggles planting-mode-active class."""
        js_code = r"""
        const fs = require('fs');
        const content = fs.readFileSync(process.argv[1], 'utf-8');

        class ClassList {
            constructor() { this.classes = new Set(); }
            add(c) { this.classes.add(c); }
            remove(c) { this.classes.delete(c); }
            contains(c) { return this.classes.has(c); }
            toggle(c, force) {
                if (force === undefined) force = !this.classes.has(c);
                if (force) this.classes.add(c);
                else this.classes.delete(c);
                return force;
            }
        }

        const elements = {
            speedNumberInput: { value: '5' },
            speedRangeSlider: { value: '5', min: '1', max: '100' },
            speedDisplayBadge: { innerText: '', classList: new ClassList() },
            speedPresetWalk: { classList: new ClassList() },
            speedPresetBike: { classList: new ClassList() },
            speedPresetDrive: { classList: new ClassList() },
            speedControlWidget: { classList: new ClassList() }
        };

        global.window = global;
        global.document = {
            getElementById: function(id) {
                return elements[id] || null;
            }
        };

        const syncMatch = content.match(/function syncSpeedControls\([\s\S]*?\n\}/);
        if (!syncMatch) {
            console.error("syncSpeedControls function not found");
            process.exit(1);
        }
        eval(syncMatch[0]);

        // 1. Test planting speed (19.1 km/h)
        syncSpeedControls(19.1);
        const resPlanting = {
            widgetPlantingActive: elements.speedControlWidget.classList.contains('planting-mode-active'),
            bikeActive: elements.speedPresetBike.classList.contains('active'),
            walkActive: elements.speedPresetWalk.classList.contains('active'),
            driveActive: elements.speedPresetDrive.classList.contains('active')
        };

        // 2. Test walk speed (5.0 km/h)
        syncSpeedControls(5.0);
        const resWalk = {
            widgetPlantingActive: elements.speedControlWidget.classList.contains('planting-mode-active'),
            bikeActive: elements.speedPresetBike.classList.contains('active'),
            walkActive: elements.speedPresetWalk.classList.contains('active'),
            driveActive: elements.speedPresetDrive.classList.contains('active')
        };

        console.log(JSON.stringify({ planting: resPlanting, walk: resWalk }));
        """

        result = subprocess.run(
            ["node", "-e", js_code, str(self.template_path)],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        # When 19.1 is set, planting-mode-active must be true on widget and Planting Speed preset active
        self.assertTrue(data["planting"]["widgetPlantingActive"], "widget must have planting-mode-active when speed is 19.1")
        self.assertTrue(data["planting"]["bikeActive"], "Planting Speed preset must be active when speed is 19.1")
        self.assertFalse(data["planting"]["walkActive"])

        # When 5.0 is set, planting-mode-active must be false
        self.assertFalse(data["walk"]["widgetPlantingActive"], "widget must NOT have planting-mode-active when speed is 5.0")
        self.assertTrue(data["walk"]["walkActive"], "walk preset must be active when speed is 5.0")
        self.assertFalse(data["walk"]["bikeActive"])

        # CSS contains blossom pink (#E8829C) active styling
        self.assertIn("#E8829C", self.content)
        self.assertTrue(
            re.search(r"planting-mode-active[^{]*\{[^}]*#E8829C", self.content) or
            re.search(r"#speedPresetBike\.active", self.content),
            "CSS must define blossom pink styling for planting mode"
        )

    def test_backward_compatibility_strings_preserved(self):
        """Backward compatibility strings remain present in template content/attributes."""
        self.assertIn("Walk (5 km/h)", self.content)
        self.assertIn("19.1 km/h", self.content)
        self.assertIn("Drive (60 km/h)", self.content)
        self.assertIn("Auto Navigation", self.content)
        self.assertIn("lni-direction-alt", self.content)
        self.assertIn("lni-target", self.content)


if __name__ == "__main__":
    unittest.main()
