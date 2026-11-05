import re
import sys
import unittest
from pathlib import Path

# Ensure src is in python path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import main


class TestBentoThemeLocalization(unittest.TestCase):
    """Ticket 01 test suite: Bento shell, botanical theme, and localization."""

    def setUp(self):
        self.app = main.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

        self.template_path = Path(__file__).resolve().parent.parent / "src" / "templates" / "map.html"
        self.map2_path = Path(__file__).resolve().parent.parent / "src" / "templates" / "map2.html"
        self.content = self.template_path.read_text(encoding="utf-8")

    def test_page_title_and_brand_header(self):
        """GET / renders title '<title>🌸 花徑漫步</title>' and brand header '🌸 花徑漫步' without old subtitle."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("<title>🌸 花徑漫步</title>", html)
        self.assertIn("🌸 花徑漫步", html)
        self.assertNotIn("GeoPort - Your location, Anywhere!", html)

    def test_obsolete_map2_template_removed(self):
        """map2.html must be removed from the repository."""
        self.assertFalse(self.map2_path.exists(), "src/templates/map2.html should be removed")

    def test_duplicate_bootstrap4_removed(self):
        """Bootstrap 4.3.1 link must be removed, leaving Bootstrap 5."""
        self.assertNotIn("stackpath.bootstrapcdn.com/bootstrap/4.3.1", self.content)
        self.assertIn("bootstrap@5", self.content)

    def test_botanical_css_variables_light_and_dark_mode(self):
        """Botanical CSS variables for Light Mode and Dark Mode must be defined."""
        # Light mode palette
        self.assertIn("#FAF8F5", self.content)
        self.assertIn("#6B9E78", self.content)
        self.assertIn("#E8829C", self.content)

        # Dark mode palette
        self.assertIn("#1E2522", self.content)
        self.assertIn("#28312C", self.content)

    def test_three_tier_bento_card_layout_structure(self):
        """Layout must contain Three-Tier Bento Card structure (Top Bar, Map Canvas, Bottom Bar)."""
        response = self.client.get("/")
        html = response.get_data(as_text=True)

        # Bento shell container
        self.assertTrue(
            "bento-container" in html or "bento-shell" in html,
            "A bento shell container must wrap the Three-Tier layout"
        )
        # Top Bento Bar
        self.assertTrue(
            "bento-top-bar" in html or "bento-card-top" in html,
            "Top Bento Bar card must exist"
        )
        # Center Map Bento Card
        self.assertTrue(
            "bento-map-card" in html or "bento-card-map" in html,
            "Center Map Bento Card must exist"
        )
        # Bottom Bento Bar
        self.assertTrue(
            "bento-bottom-bar" in html or "bento-card-bottom" in html,
            "Bottom Bento Bar card must exist"
        )

    def test_traditional_chinese_ui_labels(self):
        """All user-facing UI labels must be in friendly Traditional Chinese."""
        response = self.client.get("/")
        html = response.get_data(as_text=True)

        # Top Bar labels
        self.assertIn("📱 選擇裝置", html)
        self.assertIn("🔄 重新整理", html)
        self.assertIn("🔗 連線裝置", html)
        self.assertIn("🔌 中斷連線", html)
        self.assertIn("🌙 深色模式", html)
        self.assertIn("🚪 離開", html)

        # Bottom Bar labels
        self.assertIn("🔍 輸入座標 (lat, lng) 或搜尋地名…", html)
        self.assertIn("🔍 搜尋", html)
        self.assertIn("📍 開始定位", html)
        self.assertIn("🛑 停止定位", html)

        # Context menu starting point
        self.assertIn("📌 設為預設起點", html)

        # Connection states and helper
        self.assertIn("連線中，請稍候…", html)
        self.assertIn("✅ 已連線", html)
        self.assertIn("function isDeviceConnected", self.content)

        # Toast headers & modals
        self.assertIn("伺服器已關閉", html)
        self.assertIn("無配對紀錄", html)
        self.assertIn("連線逾時", html)

    def test_required_dom_ids_preserved(self):
        """All critical DOM IDs must be preserved for backward compatibility and script wiring."""
        static_ids = [
            "device",
            "refresh",
            "connect",
            "connectText",
            "spinner",
            "disconnect",
            "rsdData",
            "darkModeSwitch",
            "exit-btn",
            "speedControlWidget",
            "speedDisplayBadge",
            "speedPresetWalk",
            "speedPresetBike",
            "speedPresetDrive",
            "speedRangeSlider",
            "speedNumberInput",
            "navigationHud",
            "navStatusBadge",
            "navHudSpeed",
            "navHudDistance",
            "navHudEta",
            "navPauseResumeBtn",
            "navStopBtn",
            "coordinates",
            "search",
            "set-location",
            "stop-location",
            "map",
        ]
        for dom_id in static_ids:
            with self.subTest(dom_id=dom_id):
                self.assertIn(f'id="{dom_id}"', self.content)

        # Dynamic / Leaflet EasyButton IDs
        self.assertIn("autoNavButton", self.content)
        self.assertIn("cameraFollowButton", self.content)

    def test_backward_compatibility_strings_preserved(self):
        """Critical substrings expected by existing tests and scripts must remain present."""
        compat_strings = [
            "Walk (5 km/h)",
            "19.1 km/h",
            "Drive (60 km/h)",
            "Auto Navigation",
            "lni-direction-alt",
            "lni-target",
            "geoport_starting_lat",
            "geoport_starting_lng",
            "geoport_starting_zoom",
            "geoport_speed_kmh",
            "syncSpeedControls",
            "setSpeed",
        ]
        for s in compat_strings:
            with self.subTest(substr=s):
                self.assertIn(s, self.content)


if __name__ == "__main__":
    unittest.main()
