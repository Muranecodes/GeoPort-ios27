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


class TestBilingualSwitching(unittest.TestCase):
    """Test suite for Chinese/English (zh-TW / en) language switching, auto-detection, live state reactivity, and backend message translation."""

    @classmethod
    def setUpClass(cls):
        cls.template_path = Path(__file__).resolve().parent.parent / "src" / "templates" / "map.html"
        cls.content = cls.template_path.read_text(encoding="utf-8")

    def _eval_i18n_js(self, js_snippet):
        runner_script = f"""
        const fs = require('fs');
        const content = fs.readFileSync(process.argv[1], 'utf-8');

        const i18nMatch = content.match(/\\/\\/============================ i18n Localization \\(zh-TW \\/ en\\) ======================[\\s\\S]*?window\\.isDeviceConnected = isDeviceConnected;/);
        if (!i18nMatch) {{
            console.error("i18n block not found");
            process.exit(1);
        }}

        global.window = global;
        const storage = new Map();
        global.localStorage = {{
            getItem: (k) => storage.has(k) ? storage.get(k) : null,
            setItem: (k, v) => storage.set(k, String(v)),
            removeItem: (k) => storage.delete(k),
            clear: () => storage.clear()
        }};
        Object.defineProperty(global, 'navigator', {{
            value: {{ language: 'zh-TW', languages: ['zh-TW'] }},
            writable: true,
            configurable: true
        }});

        const elementsById = {{}};
        const queryAllItems = {{
            '[data-i18n]': [],
            '[data-i18n-placeholder]': [],
            '[data-i18n-title]': [],
            '.toast-body[data-raw-msg]': []
        }};

        function makeEl(id, i18nKey, initialText = '') {{
            const attrs = {{}};
            if (i18nKey) attrs['data-i18n'] = i18nKey;
            const el = {{
                id: id,
                innerText: initialText,
                textContent: initialText,
                placeholder: '',
                title: '',
                getAttribute: (k) => attrs[k] || null,
                setAttribute: (k, v) => {{ attrs[k] = v; }},
                querySelector: function(sel) {{ return this._childSpan || null; }}
            }};
            if (id) elementsById[id] = el;
            if (i18nKey) queryAllItems['[data-i18n]'].push(el);
            return el;
        }}

        global.document = {{
            title: '🌸 花徑漫步',
            documentElement: {{ lang: 'zh-TW' }},
            getElementById: (id) => elementsById[id] || null,
            querySelectorAll: (sel) => queryAllItems[sel] || []
        }};

        // Populate key DOM elements
        makeEl('brandTitle', 'brand.title', '🌸 花徑漫步');
        makeEl('selectDeviceLabel', 'top.select_device', '📱 選擇裝置');
        makeEl('refresh', 'top.refresh', '🔄 重新整理');
        makeEl('connectText', null, '🔗 連線裝置');
        makeEl('disconnect', 'top.disconnect', '🔌 中斷連線');
        makeEl('darkModeLabel', 'top.dark_mode', '🌙 深色模式');
        makeEl('langSwitchBtn', null, '🌐 EN');
        const exitBtn = makeEl('exit-btn', 'top.exit', '🚪 離開');
        exitBtn.setAttribute('data-i18n-title', 'brand.title');
        queryAllItems['[data-i18n-title]'].push(exitBtn);

        makeEl('speedControlTitle', 'speed.title', '移動速度');
        makeEl('speedPresetWalk', 'speed.walk', '🚶 散步 (5 km/h)');
        makeEl('speedPresetBike', 'speed.plant', '🌸 種花 (19.1 km/h)');
        makeEl('speedPresetDrive', 'speed.drive', '🚗 開車 (60 km/h)');

        makeEl('navHudTitle', 'hud.title', '自動導航');
        makeEl('navStatusBadge', null, '運行中');
        makeEl('navPauseResumeBtn', null, '暫停');
        makeEl('navStopBtn', 'hud.stop', '停止導航');

        const coordsInput = makeEl('coordinates', null, '');
        coordsInput.setAttribute('data-i18n-placeholder', 'bottom.coordinates_placeholder');
        queryAllItems['[data-i18n-placeholder]'].push(coordsInput);
        makeEl('search', 'bottom.search', '🔍 搜尋');
        makeEl('set-location', 'bottom.start_location', '📍 開始定位');
        makeEl('stop-location', 'bottom.stop_location', '🛑 停止定位');

        const autoNavSpan = makeEl(null, 'map.auto_nav', '自動導航');
        const autoNavBtn = makeEl('autoNavButton', null, '');
        autoNavBtn._childSpan = autoNavSpan;

        const cameraFollowSpan = makeEl(null, 'map.camera_follow', '鏡頭跟隨');
        const cameraFollowBtn = makeEl('cameraFollowButton', null, '');
        cameraFollowBtn._childSpan = cameraFollowSpan;

        makeEl('shutdownModalLabel', 'modal.shutdown.title', '伺服器已關閉');
        makeEl('shutdownModalBody', 'modal.shutdown.body', '感謝您的使用，祝您散步愉快！🌸');

        eval(i18nMatch[0]);

        {js_snippet}
        """
        result = subprocess.run(
            ["node", "-e", runner_script, str(self.template_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        return json.loads(result.stdout)

    def test_language_switcher_pill_button_present_in_utility_cluster(self):
        """Top bar utility cluster contains #langSwitchBtn pill button with toggleLocale() handler."""
        self.assertIn('id="langSwitchBtn"', self.content)
        self.assertIn('onclick="toggleLocale()"', self.content)
        self.assertIn("🌐 EN", self.content)

    def test_resolve_initial_locale_auto_detection_and_storage_override(self):
        """resolveInitialLocale respects localStorage first, then navigator.language (zh* -> zh-TW, else en)."""
        js = """
        // 1. No localStorage, navigator.language = 'en-US' -> 'en'
        localStorage.clear();
        navigator.language = 'en-US';
        const autoEn = resolveInitialLocale();

        // 2. No localStorage, navigator.language = 'ja-JP' -> 'en'
        navigator.language = 'ja-JP';
        const autoJa = resolveInitialLocale();

        // 3. No localStorage, navigator.language = 'zh-TW' -> 'zh-TW'
        navigator.language = 'zh-TW';
        const autoZhTw = resolveInitialLocale();

        // 4. No localStorage, navigator.language = 'zh-CN' -> 'zh-TW'
        navigator.language = 'zh-CN';
        const autoZhCn = resolveInitialLocale();

        // 5. localStorage overrides navigator.language
        navigator.language = 'zh-TW';
        localStorage.setItem('geoport_locale', 'en');
        const storedEn = resolveInitialLocale();

        navigator.language = 'en-US';
        localStorage.setItem('geoport_locale', 'zh-TW');
        const storedZh = resolveInitialLocale();

        console.log(JSON.stringify({
            autoEn, autoJa, autoZhTw, autoZhCn, storedEn, storedZh
        }));
        """
        data = self._eval_i18n_js(js)
        self.assertEqual(data["autoEn"], "en")
        self.assertEqual(data["autoJa"], "en")
        self.assertEqual(data["autoZhTw"], "zh-TW")
        self.assertEqual(data["autoZhCn"], "zh-TW")
        self.assertEqual(data["storedEn"], "en")
        self.assertEqual(data["storedZh"], "zh-TW")

    def test_toggle_locale_updates_brand_controls_and_persists_preference(self):
        """Switching between zh-TW and en updates Blossom Walk brand, controls, placeholders, and localStorage."""
        js = """
        setLocale('zh-TW', true);
        const zhState = {
            locale: getLocale(),
            stored: localStorage.getItem('geoport_locale'),
            docTitle: document.title,
            langBtnText: document.getElementById('langSwitchBtn').innerText,
            langBtnTitle: document.getElementById('langSwitchBtn').title,
            selectDevice: document.getElementById('selectDeviceLabel').innerText,
            speedTitle: document.getElementById('speedControlTitle').innerText,
            plantBtn: document.getElementById('speedPresetBike').innerText,
            autoNavSpan: document.getElementById('autoNavButton')._childSpan.innerText,
            cameraSpan: document.getElementById('cameraFollowButton')._childSpan.innerText,
            coordsPlaceholder: document.getElementById('coordinates').placeholder,
            startLoc: document.getElementById('set-location').innerText,
            shutdownTitle: document.getElementById('shutdownModalLabel').innerText
        };

        toggleLocale();
        const enState = {
            locale: getLocale(),
            stored: localStorage.getItem('geoport_locale'),
            docTitle: document.title,
            langBtnText: document.getElementById('langSwitchBtn').innerText,
            langBtnTitle: document.getElementById('langSwitchBtn').title,
            selectDevice: document.getElementById('selectDeviceLabel').innerText,
            speedTitle: document.getElementById('speedControlTitle').innerText,
            plantBtn: document.getElementById('speedPresetBike').innerText,
            autoNavSpan: document.getElementById('autoNavButton')._childSpan.innerText,
            cameraSpan: document.getElementById('cameraFollowButton')._childSpan.innerText,
            coordsPlaceholder: document.getElementById('coordinates').placeholder,
            startLoc: document.getElementById('set-location').innerText,
            shutdownTitle: document.getElementById('shutdownModalLabel').innerText
        };

        console.log(JSON.stringify({ zhState, enState }));
        """
        data = self._eval_i18n_js(js)
        zh = data["zhState"]
        en = data["enState"]

        self.assertEqual(zh["locale"], "zh-TW")
        self.assertEqual(zh["stored"], "zh-TW")
        self.assertEqual(zh["docTitle"], "🌸 花徑漫步")
        self.assertEqual(zh["langBtnText"], "🌐 EN")
        self.assertEqual(zh["langBtnTitle"], "Switch to English")
        self.assertEqual(zh["plantBtn"], "🌸 種花 (19.1 km/h)")
        self.assertEqual(zh["autoNavSpan"], "自動導航")
        self.assertEqual(zh["cameraSpan"], "鏡頭跟隨")

        self.assertEqual(en["locale"], "en")
        self.assertEqual(en["stored"], "en")
        self.assertEqual(en["docTitle"], "🌸 Blossom Walk")
        self.assertEqual(en["langBtnText"], "🌐 中文")
        self.assertEqual(en["langBtnTitle"], "切換至繁體中文")
        self.assertEqual(en["selectDevice"], "📱 Device")
        self.assertEqual(en["speedTitle"], "Speed")
        self.assertEqual(en["plantBtn"], "🌸 Plant (19.1 km/h)")
        self.assertEqual(en["autoNavSpan"], "Auto Navigation")
        self.assertEqual(en["cameraSpan"], "Camera Tracking")
        self.assertEqual(en["coordsPlaceholder"], "🔍 Enter coordinates (lat, lng) or search place…")
        self.assertEqual(en["startLoc"], "📍 Start Location")
        self.assertEqual(en["shutdownTitle"], "Server Shut Down")

    def test_live_switching_preserves_dynamic_connection_and_hud_states(self):
        """Switching language mid-session updates dynamic connection states and Navigation HUD states without reload."""
        js = """
        // Simulate connected device and paused navigation in zh-TW
        setLocale('zh-TW', false);
        document.getElementById('connectText').innerText = '✅ 已連線';
        window.navPaused = true;
        window.isAutoNavMode = true;
        window.isCameraLocked = false;

        // Switch to English live
        setLocale('en', true);
        const enConnected = {
            connectText: document.getElementById('connectText').innerText,
            isConnected: isDeviceConnected(),
            navBadge: document.getElementById('navStatusBadge').innerText,
            navPauseBtn: document.getElementById('navPauseResumeBtn').innerText,
            autoNavTitle: document.getElementById('autoNavButton').title,
            cameraTitle: document.getElementById('cameraFollowButton').title
        };

        // Switch back to zh-TW while navigation is running (unpaused)
        window.navPaused = false;
        setLocale('zh-TW', true);
        const zhRunning = {
            connectText: document.getElementById('connectText').innerText,
            isConnected: isDeviceConnected(),
            navBadge: document.getElementById('navStatusBadge').innerText,
            navPauseBtn: document.getElementById('navPauseResumeBtn').innerText,
            autoNavTitle: document.getElementById('autoNavButton').title,
            cameraTitle: document.getElementById('cameraFollowButton').title
        };

        console.log(JSON.stringify({ enConnected, zhRunning }));
        """
        data = self._eval_i18n_js(js)
        en = data["enConnected"]
        zh = data["zhRunning"]

        self.assertEqual(en["connectText"], "✅ Connected")
        self.assertTrue(en["isConnected"])
        self.assertEqual(en["navBadge"], "Paused")
        self.assertEqual(en["navPauseBtn"], "Resume")
        self.assertEqual(en["autoNavTitle"], "Auto Navigation (Active)")
        self.assertEqual(en["cameraTitle"], "Camera Tracking (Unlocked)")

        self.assertEqual(zh["connectText"], "✅ 已連線")
        self.assertTrue(zh["isConnected"])
        self.assertEqual(zh["navBadge"], "運行中")
        self.assertEqual(zh["navPauseBtn"], "暫停")
        self.assertEqual(zh["autoNavTitle"], "自動導航 (已開啟)")
        self.assertEqual(zh["cameraTitle"], "鏡頭跟隨 (已解鎖)")

    def test_backend_message_translation_and_error_prefix_handling(self):
        """translateBackendMessage localizes known backend responses and preserves unknown error details after localized prefixes."""
        js = """
        setLocale('zh-TW', false);
        const zhMsgs = {
            setSuccess: translateBackendMessage('DVT set call completed; check the phone location'),
            clearSuccess: translateBackendMessage('Location cleared successfully'),
            errKnown: translateBackendMessage('Location failed: No iOS version present'),
            errUnknown: translateBackendMessage('Location failed: Custom USB timeout 0x99')
        };

        setLocale('en', false);
        const enMsgs = {
            setSuccess: translateBackendMessage('DVT set call completed; check the phone location'),
            clearSuccess: translateBackendMessage('Location cleared successfully'),
            errKnown: translateBackendMessage('定位失敗：No iOS version present'),
            errUnknown: translateBackendMessage('定位失敗：Custom USB timeout 0x99')
        };

        console.log(JSON.stringify({ zhMsgs, enMsgs }));
        """
        data = self._eval_i18n_js(js)
        self.assertEqual(data["zhMsgs"]["setSuccess"], "📍 定位已更新，請確認手機位置")
        self.assertEqual(data["zhMsgs"]["clearSuccess"], "🛑 已清除定位模擬")
        self.assertEqual(data["zhMsgs"]["errKnown"], "定位失敗：無法取得裝置 iOS 版本，請先連線裝置")
        self.assertEqual(data["zhMsgs"]["errUnknown"], "定位失敗：Custom USB timeout 0x99")

        self.assertEqual(data["enMsgs"]["setSuccess"], "📍 Location updated; please check your device")
        self.assertEqual(data["enMsgs"]["clearSuccess"], "🛑 Location cleared successfully")
        self.assertEqual(data["enMsgs"]["errKnown"], "Location failed: No iOS version present; please connect a device first")
        self.assertEqual(data["enMsgs"]["errUnknown"], "Location failed: Custom USB timeout 0x99")


if __name__ == "__main__":
    unittest.main()
