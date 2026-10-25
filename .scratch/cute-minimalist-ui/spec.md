# Spec: Cute Minimalist Web UI Redesign (「花徑漫步」簡約可愛介面重設計)

Status: completed

## Problem Statement

Users of the workbench currently interact with an engineering-heavy, visually fragmented web interface that mixes conflicting Bootstrap versions, default stark blue form controls, and inconsistent English and Traditional Chinese labels. 

Specifically, from the user's perspective:
1. **Visual Fatigue and Harsh Styling**: The stark white/gray backgrounds and saturated `#007bff` buttons feel like a raw developer utility rather than a cozy, pleasant companion for strolling and flower planting.
2. **Wasted Vertical Space and Scrolling**: The page stacks the title, dark mode toggle, device selector, connection buttons, a fixed-height map, coordinate search, and simulation buttons vertically in separate rows, requiring unnecessary scrolling on standard laptop screens.
3. **Cluttered Map Toolbar**: The top-left map control bar stacks 7 icon-only buttons—including unused GPX upload/save/playback tools, track drawing, marker clearing, and a legacy speed dropdown that duplicates the floating speed widget—obscuring the two controls users actually rely on (**Auto Navigation** and **Camera Tracking**).
4. **Inconsistent Language and Outdated Identity**: The UI mixes English labels (`Select Device:`, `Connect Device`, `Simulate Location`, `Walk (5 km/h)`) with Traditional Chinese (`🌸 種花 (19.1 km/h)`, `自動導航`), and still bears the generic "GeoPort" title even though the product experience has evolved into a specialized strolling and flower-planting workbench.
5. **Template Duplication**: An obsolete secondary HTML template remains in the repository without supporting modern **Auto Navigation**, **Manual Steering**, or **Planting Speed** features, creating maintenance confusion.

## Solution

Transform the web interface into **「🌸 花徑漫步」**—a cohesive, single-screen, minimalist-and-cute workbench inspired by a soft Japanese botanical aesthetic (Pastel Sage & Blossom on Warm Cream, with a Cozy Forest Night dark mode):

1. **New Brand Identity & Unified Traditional Chinese Copy**: Rebrand all user-facing titles, headers, toast notifications, and modal dialogs to **「🌸 花徑漫步」** (without a subtitle) and unify all UI labels into friendly Traditional Chinese paired with cute icons/emojis.
2. **Three-Tier Compact Bento Card Layout**: Consolidate the interface into three rounded, non-scrolling Bento sections that fit comfortably within a single viewport:
   - **Top Bar Card**: Single horizontal row housing the `🌸 花徑漫步` brand title on the left, device selection (`📱 選擇裝置`), refresh (`🔄 重新整理`), and connect/disconnect (`🔗 連線裝置` / `🔌 中斷連線`) in the center, and dark mode toggle (`🌙 深色模式`) plus exit (`🚪 離開`) on the right.
   - **Center Map Canvas**: A large, extra-rounded map container (`24px` radius) that dynamically fills remaining viewport height, defaulting to the soft pastel `CartoDB Voyager` base map and rendering **Auto Navigation** routes as a smooth sage-green path.
   - **Bottom Bar Card**: Single horizontal row combining the coordinate/place search input (`🔍 輸入座標或地名…`) and search button (`搜尋`) with pill-shaped **Location Simulation** action buttons (`📍 開始定位` and `🛑 停止定位`).
3. **Decluttered Map Controls with Pill Labels**: Hide the 5 unused legacy map toolbar buttons (GPX upload, GeoJSON save, GPX playback, polyline draw, legacy speed menu, and clear markers) via CSS while preserving their DOM nodes for backward compatibility. Style the remaining two primary controls—**Auto Navigation** (`🧭 自動導航`) and **Camera Tracking** (`🎯 鏡頭跟隨`)—as cute, readable icon-plus-text pill buttons.
4. **Botanical Speed & Navigation Floating Cards**: Restyle the top-right floating speed widget and **Auto Navigation** HUD as soft rounded floating cards. Give the **Planting Speed** preset (`🌸 種花 19.1 km/h`) a signature blossom-pink active theme (`#F299B1` / `#E8829C`), while walking (`🚶 散步 5 km/h`) and driving (`🚗 開車 60 km/h`) presets use soft sage green (`#6B9E78`).
5. **Cozy Forest Night Dark Mode & Legacy Template Cleanup**: Replace the harsh `#222` dark mode with a warm forest-night palette (`#1E2522` background, `#28312C` cards, soft mint and blossom accents) and remove the obsolete secondary map template.

## User Stories

1. As a user opening the workbench in my browser, I want to see the brand name **「🌸 花徑漫步」** in the browser tab and top header without a cluttered subtitle, so that the app feels like a dedicated, charming strolling companion.
2. As a user on a laptop or desktop screen, I want the top device bar, central map canvas, and bottom location bar to fit within a single viewport without vertical scrolling, so that I can see and operate every control at a glance.
3. As a user sensitive to visual glare, I want a warm cream background (`#FAF8F5`), soft sage green primary accents, and rounded card surfaces with diffused shadows in light mode, so that long sessions watching the map remain comfortable on my eyes.
4. As a night-time user, I want toggling dark mode (`🌙 深色模式`) to switch the entire workbench—including Bento cards, inputs, floating HUDs, modals, and toasts—into a cozy forest-night palette (`#1E2522` / `#28312C`), so that the interface stays warm and readable in low light.
5. As a user connecting an iOS device, I want the device dropdown, refresh button, and connect/disconnect buttons arranged inline inside the top Bento card with clear Traditional Chinese labels (`📱 選擇裝置`, `🔄 重新整理`, `🔗 連線裝置`, `🔌 中斷連線`), so that hardware setup takes minimal screen space.
6. As a user waiting for a device tunnel to establish, I want the connect button to show a friendly Traditional Chinese loading state (`連線中，請稍候…`) with a spinner and transition to `✅ 已連線` when ready, so that connection progress is immediately clear.
7. As a user looking at the map, I want the default base map to load with `CartoDB Voyager` tiles while keeping the layer switcher available, so that the map colors harmonize naturally with the pastel UI out of the box.
8. As a user scanning the top-left of the map, I want to see only the **Auto Navigation** (`🧭 自動導航`) and **Camera Tracking** (`🎯 鏡頭跟隨`) pill buttons—with unused GPX, drawing, legacy speed menu, and trash buttons hidden—so that I never misclick irrelevant tools.
9. As a user toggling **Auto Navigation** or **Camera Tracking**, I want each button to display both an icon and a short Traditional Chinese label inside a rounded pill that highlights clearly when active, so that I can tell immediately whether targeting mode or viewport lock is engaged.
10. As a player using **Planting Speed** (`🌸 種花 19.1 km/h`), I want selecting the 19.1 km/h preset to highlight the preset button and speed badge in a signature blossom-pink theme, so that flower-planting mode feels distinct and celebratory compared to standard walking or driving speeds.
11. As a user adjusting movement speed, I want the floating speed control card to display `🚶 散步 (5 km/h)`, `🌸 種花 (19.1 km/h)`, and `🚗 開車 (60 km/h)` alongside a smooth range slider and numeric km/h input, so that both quick preset switching and fine speed tuning are effortless.
12. As a user running **Auto Navigation**, I want the active route polyline on the map to render in a soft, rounded sage-green stroke rather than harsh default blue, so that the planned path blends harmoniously with the botanical theme.
13. As a user monitoring an active **Auto Navigation** trip, I want the floating navigation HUD card to match the rounded botanical card style and clearly show running/paused status badges (`運行中` / `已暫停`), current speed, remaining distance, ETA, and pill buttons for `暫停`/`繼續` and `停止導航`, so that trip progress is easy to read.
14. As a user searching for a destination or entering coordinates, I want the search box (`🔍 輸入座標或地名…`), `搜尋` button, `📍 開始定位` button, and `🛑 停止定位` button aligned in a single compact bottom Bento card, so that manual teleportation and **Location Simulation** controls are always within reach below the map.
15. As a user right-clicking on the map to save a default starting location, I want the popup button (`📌 設為預設起點`) and confirmation toast (`已儲存預設起點`) styled in the same rounded Traditional Chinese aesthetic, so that context-menu interactions feel cohesive.
16. As a user encountering system dialogs (Developer Mode required, passcode warning, missing pair record, connection timeout, or server shutdown), I want all modal dialogs and toast notifications to display friendly Traditional Chinese messages and rounded botanical styling, so that error recovery is clear and non-intimidating.
17. As a returning user, I want my previously saved starting coordinates (`geoport_starting_lat`, `geoport_starting_lng`, `geoport_starting_zoom`) and speed setting (`geoport_speed_kmh`) in `localStorage` to continue working seamlessly after the redesign, so that my preferences are not lost.
18. As a developer maintaining the repository, I want the unused legacy secondary HTML template removed, so that there is a single source of truth for the web interface.

## Implementation Decisions

### 1. Modules to Modify and Clean Up
- **Primary Web UI Template**: Overhaul the CSS styling, layout grid, HTML copy, Leaflet control initialization, and theme state classes within the active map template served by the Flask root route.
- **Obsolete Secondary Template Removal**: Delete the unused secondary map template from the templates directory so only a single canonical template exists.

### 2. Visual Design System & CSS Custom Properties
- Define a clean set of CSS variables on `:root` and `body.dark-mode`:
  - **Light Mode (Botanical Cream)**:
    - Background surface: `#FAF8F5` (warm ivory cream)
    - Card surface: `rgba(255, 255, 255, 0.92)` with subtle border `#E6E2D8` and soft shadow `0 8px 24px rgba(92, 107, 97, 0.08)`
    - Primary accent (Sage Green): `#6B9E78` (hover `#5A8B66`, soft tint `#EAF3EC`)
    - Blossom accent (**Planting Speed** / Secondary highlight): `#E8829C` (soft fill `#FCEEF2`, border `#F4B8C8`)
    - Danger / Stop action: `#E07A7A` (soft coral red)
    - Text hierarchy: primary `#2F3A34`, secondary `#6E7B73`
  - **Dark Mode (Cozy Forest Night)**:
    - Background surface: `#1E2522`
    - Card surface: `rgba(40, 49, 44, 0.94)` with border `#38453E` and shadow `0 8px 24px rgba(0, 0, 0, 0.35)`
    - Primary accent (Mint Sage): `#7FB38D`
    - Blossom accent: `#F299B1`
    - Text hierarchy: primary `#ECF2EE`, secondary `#A3B1A8`
- **Typography & Geometry**:
  - Use rounded, friendly sans-serif font stack (`"Nunito"`, `"M PLUS Rounded 1c"`, `"Noto Sans TC"`, `"PingFang TC"`, `"Microsoft JhengHei"`, sans-serif).
  - Card border-radius: `20px–24px`; interactive buttons and inputs: pill-shaped (`border-radius: 999px`) with subtle active press feedback (`transform: translateY(1px)`).
  - Remove the duplicate Bootstrap 4 stylesheet link so only Bootstrap 5 and custom botanical styles apply.

### 3. Three-Tier Bento Layout Architecture
- Wrap the page in a full-height flex column container (`height: 100vh; max-height: 100vh; padding: 12px 16px; gap: 10px; box-sizing: border-box`) that adapts gracefully on smaller viewports:
  - **Tier 1 (Top Bento Card)**: Compact horizontal flex bar containing:
    - Brand cluster: `🌸 花徑漫步`
    - Device cluster: `#device` select dropdown, `#refresh` button (`🔄 重新整理`), `#connect` button (`🔗 連線裝置`), `#disconnect` button (`🔌 中斷連線`), and hidden `#rsdData` state input.
    - Utility cluster: `#darkModeSwitch` toggle (`🌙 深色模式`) and `#exit-btn` (`🚪 離開`).
  - **Tier 2 (Map Canvas Card)**: `#map` flexes to fill all remaining vertical space (`flex: 1; min-height: 380px; border-radius: 24px; overflow: hidden`).
  - **Tier 3 (Bottom Bento Card)**: Compact horizontal flex bar containing:
    - Search cluster: `#coordinates` input (`placeholder="輸入座標 (lat, lng) 或搜尋地名…"`) and `#search` button (`🔍 搜尋`).
    - Simulation cluster: `#set-location` button (`📍 開始定位`) and `#stop-location` button (`🛑 停止定位`).

### 4. Map Controls, Base Layer, and HUD Refinements
- **Default Tile Layer**: Add `CartoDB_Voyager` to the map as the initial active tile layer on startup while keeping `Stadia Maps`, `OpenStreetMap`, and other layers selectable in `L.control.layers`.
- **Top-Left Toolbar Decluttering**:
  - Keep `#autoNavButton` and `#cameraFollowButton` visible and upgrade their inner HTML to display both their required LineIcons (`<i class="lni lni-direction-alt"></i>` and `<i class="lni lni-target"></i>`) and concise Chinese labels (`<span>自動導航</span>` and `<span>鏡頭跟隨</span>`), styled as horizontal pill buttons.
  - Hide the unused controls inside `.leaflet-control-filelayer` (file upload label, `saveMapButton`, `playbackButton`, `drawPolylineButton`, `dashboardButton` / `#styles-menu`, and `customButton` trash icon) using CSS (`display: none !important`) while keeping their DOM creation intact so existing script references never throw null errors.
- **Speed Control Widget & Planting Speed Theme**:
  - Update preset buttons to display friendly Chinese labels while preserving the exact substring or attribute contracts expected by tests (e.g., `🚶 散步 · Walk (5 km/h)` or keeping `Walk (5 km/h)` / `Drive (60 km/h)` in button content/attributes).
  - In `syncSpeedControls(speed)`, toggle a dedicated `.planting-mode-active` class on `#speedControlWidget` and `#speedDisplayBadge` whenever the speed is at **Planting Speed** (`19.1 km/h`), switching the active badge and slider accent to blossom pink.
- **Auto Navigation Route Polyline**:
  - Style `window.navRoutePolyline` with a soft botanical sage green (`#6B9E78`, weight `6`, opacity `0.88`, `lineCap: 'round'`, `lineJoin: 'round'`).

### 5. Backward-Compatible DOM & State Contracts
- Preserve all existing element IDs (`#device`, `#refresh`, `#connect`, `#connectText`, `#spinner`, `#disconnect`, `#rsdData`, `#darkModeSwitch`, `#exit-btn`, `#speedControlWidget`, `#speedDisplayBadge`, `#speedPresetWalk`, `#speedPresetBike`, `#speedPresetDrive`, `#speedRangeSlider`, `#speedNumberInput`, `#navigationHud`, `#navStatusBadge`, `#navHudSpeed`, `#navHudDistance`, `#navHudEta`, `#navPauseResumeBtn`, `#navStopBtn`, `#autoNavButton`, `#cameraFollowButton`, `#coordinates`, `#search`, `#set-location`, `#stop-location`).
- Preserve all existing JS function signatures, `localStorage` keys (`geoport_starting_lat`, `geoport_starting_lng`, `geoport_starting_zoom`, `geoport_speed_kmh`), and toast message strings asserted by automated tests (`請先在地圖上設定當前位置或連線設備`, `自動導航模式已開啟：請點擊地圖目的地出發`, `自動導航模式已關閉`, `已到達目的地`, `自動導航已中斷，切換為手動操作`).

## Testing Decisions

### 1. What Makes a Good Test
Tests should verify observable contracts at the highest existing seam without coupling to fragile internal CSS rules:
- Rendered HTML structure and required interactive element IDs via the Flask test client (`GET /`).
- Presence of the new brand identity (`🌸 花徑漫步`), Traditional Chinese UI labels, `CartoDB_Voyager` default layer activation, hidden rules for unused toolbar controls, and removal of the obsolete secondary template.
- Client-side JavaScript state behavior (speed preset synchronization, **Planting Speed** blossom-pink state toggling, **Auto Navigation** mode toggling, **Camera Tracking** lock toggling, and **Manual Steering** interruption) evaluated in Node.js.

### 2. Modules to Test
- **Web UI Template & Client State**: Tested via Flask `test_client()` HTML inspection and Node.js function evaluation in the existing frontend test modules.

### 3. Prior Art in the Codebase
- Existing template and Node.js evaluation tests in the test suite (`TestMapTemplateSpeedControl`, `TestMapTemplateAutoNavVerification`, `TestCameraLockAndStateToggling`, `TestMapTemplateNavigationHud`, and `TestKeyboardSteering`).

## Out of Scope

- Changes to backend Python hardware communication, DVT tunnel management, or `pymobiledevice3` integration.
- Changes to server-side 1Hz route interpolation math or anti-burst pacing logic (covered by ADR-0001).
- Renaming internal filesystem directories (`~/GeoPort`), log filenames (`geoport.log`), or `localStorage` key prefixes.
- Deleting the underlying JavaScript functions for GPX playback or GeoJSON export (only their toolbar entry points are hidden in the UI).

## Further Notes

- Existing automated tests check for the substrings `"Walk (5 km/h)"`, `"19.1 km/h"`, `"Drive (60 km/h)"`, `"Auto Navigation"`, `"lni-direction-alt"`, and `"lni-target"` in the template source. Keeping these strings present in the template (e.g., via `title` / `aria-label` attributes or dual labels) guarantees 100% compatibility with existing regression tests alongside the new UI tests.
