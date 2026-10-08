# 02: 鍵盤 W/A/S/D 即時手動操控

**What to build:** Interactive keyboard steering on the map interface. When the user holds down W, A, S, D or the Arrow keys, the simulated position smoothly moves at the selected speed in real time, stopping immediately when the key is released.

**Blocked by:** 01: Location Sink 適配器與基礎幾何步進核心

**Status:** completed

- [x] Add global keydown and keyup event listeners for W, A, S, D, ArrowUp, ArrowLeft, ArrowDown, ArrowRight.
- [x] Implement a client-side movement ticker that sends `POST /move_step` every 1 second while any directional key is held down.
- [x] Immediately cease stepping and sending requests upon key release.
- [x] Smoothly update the Leaflet map marker position and coordinate input fields to mirror the stepped location.
- [x] Ignore keypress events when the user is focused on text inputs, textareas, or modal search fields.
