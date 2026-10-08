# 04: 後端 1Hz 背景巡航引擎、到達停止與狀態 HUD

**What to build:** A server-side 1Hz background navigation worker that interpolates along polyline waypoints at the selected speed and dispatches coordinates to the location sink, resilient to browser tab sleep or minimization, accompanied by an interactive status HUD and WASD interruption.

**Blocked by:** 03: 時速控制面板與動態調速

**Status:** completed

- [x] Implement `POST /start_navigation` accepting a list of coordinate waypoints `[[lat, lng], ...]` and `speed_kmh`.
- [x] Implement a background thread worker that ticks every 1.0 second, interpolating distance along the polyline path and sending coordinates to `LocationSink`.
- [x] Implement `POST /stop_navigation`, `POST /pause_navigation`, `POST /resume_navigation`, and `GET /navigation_status`.
- [x] When reaching the final waypoint within stepping tolerance, automatically halt navigation and mark status as completed.
- [x] Render a floating HUD on the map displaying active speed, remaining distance, ETA, pause/resume button, and stop button.
- [x] When the user presses any WASD manual key while navigation is running, automatically cancel the navigation worker and transition seamlessly to manual steering.
- [x] Add automated tests for route interpolation, state transitions, ETA calculations, and manual interruption.
