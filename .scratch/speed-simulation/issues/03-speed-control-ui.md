# 03: 時速控制面板與動態調速

**What to build:** A comprehensive speed control interface on the map containing quick presets (Walk 5 km/h, Bike 20 km/h, Drive 60 km/h) alongside a custom slider and numeric input field, allowing the user to dynamically adjust movement speed during active movement without restarting.

**Blocked by:** 02: 鍵盤 W/A/S/D 即時手動操控

**Status:** completed

- [x] Add an intuitive speed toolbar widget containing buttons for 5 km/h (Walk), 20 km/h (Bike), and 60 km/h (Drive), plus a synchronized number input and slider control.
- [x] Provide a `POST /update_speed` API endpoint accepting `{ "speed_kmh": float }` that updates the backend navigation velocity state.
- [x] Changing the speed immediately adjusts the step distance for ongoing manual WASD stepping and any active route navigation without pausing or resetting.
- [x] Fix the legacy issue in `calculateTime` where custom numeric speeds defaulted back to 6 km/h.
- [x] Persist the user's chosen speed in localStorage so it is retained across page reloads.
