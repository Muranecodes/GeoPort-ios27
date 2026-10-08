# Changelog

This project is a modified version of [GeoPort](https://github.com/davesc63/GeoPort)
by davesc63, licensed under GPL-3.0. Changes relative to the original:

## 2026-10-08
- Added Speed Simulation Movement system:
  - Auto Navigation mode with OSRM footway routing and direct-line fallback.
  - Dynamic speed controls with presets (5, 20, 60 km/h), slider, and custom numeric input.
  - Real-time WASD and Arrow keys manual movement with instant interruption of auto navigation.
  - Floating Navigation HUD with distance, ETA, speed, and Pause / Resume / Stop controls.
  - Camera auto-centering toggle button with unlocked free-panning capability.
  - Server-side 1Hz background worker thread for uninterrupted simulation in background tabs.
  - Persistent iOS DVT streaming session to avoid connection backpressure and latency.
- Fixed duplicate click event listener on Auto Navigation and Camera Tracking toolbar buttons.
- Added start coordinate validation prompt when starting navigation without prior location.

## 2026-10-06
- Removed Buy Me a Coffee donation buttons and donation text (README, `map.html`, `map2.html`).
- Removed original author's Discord, NordVPN referral, FAQ and survey links.
- Removed usage telemetry sent to `api.geoport.me` (`recordEvent`, `updateDynamoDB`).
- Removed remote broadcast banner (`get_github_broadcast`, `BROADCAST` file).
- Version check now points to `Muranecodes/GeoPort-ios27`.
- Simplified the "no devices found" error message.
