# Spec: Speed Simulation Movement (特定時速移動模擬)

Status: completed

## Problem Statement

When simulating location on iOS devices using GeoPort, users can currently teleport to fixed coordinates or step manually between points. However, users playing location-based games (such as Pokémon GO) or testing navigation and delivery apps need to simulate realistic continuous movement at specific speeds (e.g., walking, cycling, or driving) along actual roads and footpaths. 

Currently, GeoPort lacks a reliable way to:
1. Automatically follow real pedestrian road networks at a chosen speed.
2. Manually maneuver in real time using keyboard controls without abrupt coordinate jumps.
3. Keep location updates ticking when the browser tab is hidden or minimized, causing existing client-side timers to throttle or freeze.
4. Dynamically adjust movement speed mid-journey without stopping and restarting the trip.

## Solution

Provide a comprehensive Speed Simulation Movement system that combines:
1. **Auto Navigation Mode**: Users activate an Auto Navigation toggle and click any destination on the map. GeoPort automatically routes along pedestrian footways and sidewalks, then continuously advances the simulated GPS position step-by-step at a chosen speed (1 update per second).
2. **Keyboard WASD Manual Control**: Users can hold W/A/S/D (or arrow keys) to walk smoothly in cardinal directions (North, South, West, East) at the current speed setting, stopping immediately upon release. If auto-navigation is in progress, manual keypresses cleanly interrupt it to give immediate control to the user.
3. **Dynamic Speed Controls**: Quick speed presets (Walk 5 km/h, Bike 20 km/h, Drive 60 km/h) alongside custom numeric slider/input controls, allowing on-the-fly speed adjustment during active movement.
4. **Backend-Driven Dispatch Worker**: The movement interpolation and 1Hz GPS pushing are executed by a background worker thread on the server, ensuring uninterrupted movement even when the browser tab is backgrounded.
5. **Interactive HUD & Camera Tracking**: A floating status control bar displays remaining distance, ETA, current speed, and pause/resume/stop controls, while map camera auto-centers on the moving avatar with an unlockable view toggle.

## User Stories

1. As a location spoofer user, I want to set a target speed in km/h, so that my simulated movement reflects realistic travel speeds.
2. As a user, I want quick-select speed presets for Walking (5 km/h), Cycling (20 km/h), and Driving (60 km/h), so that I can switch common speeds with a single click.
3. As a user, I want a custom speed input and slider, so that I can fine-tune my movement speed to any arbitrary value.
4. As a user, I want to adjust my speed while already moving, so that I do not need to cancel and restart my journey just to speed up or slow down.
5. As a gamer, I want to toggle an "Auto Navigation" mode on the map toolbar, so that clicking on the map immediately starts routing rather than teleporting.
6. As a user, I want the route to follow pedestrian pathways using walking routing, so that my avatar travels along realistic paths rather than walking through buildings or water.
7. As a user, I want the system to fall back to straight-line interpolation if the external routing service is unreachable or when off-road, so that navigation never stalls or crashes.
8. As a user, I want the simulated GPS location to update at 1Hz (once per second), so that it mirrors standard smartphone GPS hardware behavior and avoids anti-cheat flags.
9. As a user, I want the on-screen map marker to animate smoothly between 1-second updates, so that the visual presentation is fluid and pleasant.
10. As a user, I want to pause and resume my auto-navigation trip, so that I can pause simulation temporarily while interacting with app features.
11. As a user, I want to stop auto-navigation at any time, so that I can halt movement immediately.
12. As a user, I want the simulation to stop automatically when reaching the destination, so that I do not overshoot my target.
13. As a user, I want an alert or toast notification upon arriving at the destination, so that I know my trip has completed.
14. As a user, I want a floating navigation panel showing remaining distance, estimated time of arrival (ETA), and controls, so that I can monitor trip progress.
15. As a user, I want the map viewport to automatically center on the moving location marker, so that I do not lose track of my avatar.
16. As a user, I want a button to unlock camera auto-centering, so that I can freely pan and inspect other areas of the map while still moving.
17. As a desktop user, I want to press and hold W/A/S/D to move in real-time, so that I can explore surroundings intuitively with the keyboard.
18. As a desktop user, I want releasing W/A/S/D to immediately stop manual movement, so that I have precise stopping control.
19. As a user, I want manual keyboard input to cleanly interrupt and cancel any active auto-navigation, so that I can quickly react without clicking cancel first.
20. As a user, I want continuous movement simulation to proceed unaffected when my browser tab is minimized or inactive, so that my character keeps walking in the background.
21. As a user, I want the underlying iOS DVT connection to remain open across consecutive coordinate updates, so that updates are instantaneous and do not overwhelm device connection buffers.
22. As an administrator/tester, I want API endpoints to query navigation status and inject simulated movements, so that external scripts and frontends can inspect state.

## Implementation Decisions

### 1. Modules Modified and Created
- **Navigation Controller & Movement Engine**: A server-side module responsible for route interpolation, speed math, step generation, background thread lifecycle, and coordinate dispatching.
- **Location Sink Adapter**: An abstraction layer isolating device hardware communication (DVT / pymobiledevice3) from movement calculation logic.
- **Web UI & Map Client Module**: Front-end Leaflet extensions adding the speed toolbar, auto-navigation toggle, OSRM route fetcher, floating status bar, camera follower, and keyboard input listeners.

### 2. Architectural Decisions
- **Server-Side Ticker (Backend Worker Thread)**: The 1Hz clock and path stepping are driven entirely by a background Python worker thread. The frontend receives progress updates and renders smooth client-side interpolation. This prevents browser tab throttling from pausing or lagging GPS updates.
- **Persistent DVT Channel**: The backend keeps the active location simulation session open across successive coordinate updates instead of tearing down and reconnecting SSL/DVT sockets on every coordinate push.
- **Coordinate Interpolation Engine**: Great-circle / Haversine distance calculations are used to interpolate points at exact step sizes (`distance_meters = speed_kmh / 3.6`). Between route waypoints, the worker steps forward along the polyline segments proportionally.
- **Routing Source**: Front-end requests pedestrian routes from OSRM foot routing API (`https://routing.openstreetmap.de/routed-foot/route/v1/`). If OSRM returns an error or no route, the frontend falls back to a 2-point direct path between start and end coordinates.
- **Keyboard Directional Mapping**:
  - `W` / `ArrowUp` = Heading 0° (North)
  - `S` / `ArrowDown` = Heading 180° (South)
  - `A` / `ArrowLeft` = Heading 270° (West)
  - `D` / `ArrowRight` = Heading 90° (East)
  - Distance stepped per second = `speed_kmh / 3.6` meters.

### 3. API Contracts

- **`POST /start_navigation`**
  - **Request Body**:
    ```json
    {
      "waypoints": [[lat1, lng1], [lat2, lng2], ...],
      "speed_kmh": 5.0
    }
    ```
  - **Response**: `{ "status": "started", "total_distance_m": 1250.5, "estimated_duration_s": 900 }`
  - Starts background worker thread along the polyline. Cancels any previous navigation.

- **`POST /stop_navigation`**
  - **Response**: `{ "status": "stopped", "current_location": { "lat": 12.34, "lng": 56.78 } }`
  - Halts the background worker. The device stays at the last reported coordinate.

- **`POST /pause_navigation`** and **`POST /resume_navigation`**
  - Pauses / resumes the 1Hz ticker without clearing the remaining waypoint path.

- **`POST /update_speed`**
  - **Request Body**: `{ "speed_kmh": 20.0 }`
  - **Response**: `{ "speed_kmh": 20.0, "updated_duration_s": 225 }`
  - Dynamically updates active worker speed in real time.

- **`GET /navigation_status`**
  - **Response**:
    ```json
    {
      "active": true,
      "paused": false,
      "current_lat": 12.3456,
      "current_lng": 56.7890,
      "speed_kmh": 5.0,
      "remaining_distance_m": 420.5,
      "remaining_time_s": 302,
      "completed": false
    }
    ```

- **`POST /move_step`**
  - **Request Body**: `{ "direction": "w" | "a" | "s" | "d", "speed_kmh": 5.0 }`
  - **Response**: `{ "lat": 12.3458, "lng": 56.7890 }`
  - Immediately steps one second's worth of distance in the given direction. If auto-navigation is active, it is automatically stopped.

### 4. UI Interaction & Component Layout
- **Toolbar Addition**: Add an "Auto Navigation" icon button in the Leaflet control bar. When active, clicking on the map plans a route and triggers `/start_navigation`.
- **Speed Selector Widget**: Compact control displaying presets (5 km/h, 20 km/h, 60 km/h), a numeric text field, and a slider.
- **Floating HUD (Bottom Center / Top Right)**: Displays current speed, remaining distance, ETA timer, Pause/Resume toggle, and Stop button. Automatically collapses when navigation ends.
- **Camera Center Lock Button**: Toggleable button on the map to switch between locking map center to marker and free panning.

## Testing Decisions

### 1. Definition of a Good Test
Tests must verify observable external behavior and contracts rather than internal private state. They should test:
- Correct HTTP status codes and response schemas from API endpoints.
- Path interpolation accuracy (total distance traveled matches expected speed over time).
- Correct state transitions (started → paused → resumed → completed).
- Concurrency and conflict handling (manual step interrupting auto navigation).
- Fault tolerance (invalid speeds, empty routes, coordinate bounds).

### 2. Modules to Test
- **Navigation Controller**: Unit and integration tests for route stepping math, waypoint advancement, and worker pause/resume/stop lifecycle.
- **Flask Route Endpoints**: Integration tests via Flask `test_client()` exercising all navigation and speed endpoints with a mock `LocationSink`.
- **Geometry & Distance Utilities**: Edge cases in Haversine distance, bearing calculations, and coordinate destination projections.

### 3. Prior Art & Mocking Strategy
- Use an in-memory `MockLocationSink` implementing the sink interface to capture location dispatches without requiring a connected iOS device or DVT service.
- Use `time.sleep` or simulated clock stepping in tests to verify timed ticker behavior deterministically.

## Out of Scope

- Vehicle route profile switching (strict pedestrian footway routing is used as agreed).
- Round-trip looping or continuous lap repetition (single trip arrival and stop only).
- Touchscreen on-screen virtual joystick overlay (pure keyboard WASD controls).
- Altitude / elevation simulation.
- Multi-device concurrent synchronization (navigation controls operate on the currently active device session).

## Further Notes

- The existing `calculateTime` function in `src/templates/map.html` had a known bug where numeric custom speeds fell back to walking 6 km/h. This implementation replaces front-end time calculations with backend velocity and distance calculations.
- OSRM public demo server rate limits should be respected by caching calculated route geometry client-side for the duration of the trip.
