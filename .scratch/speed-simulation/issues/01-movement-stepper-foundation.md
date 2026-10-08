# 01: Location Sink 適配器與基礎幾何步進核心

**What to build:** An abstract location sink interface and coordinate projection calculation engine, allowing location simulation coordinates to be stepped in cardinal directions (North, South, East, West) at specified speeds without direct hardware coupling, verified by a new `/move_step` HTTP endpoint and unit tests.

**Blocked by:** None (can start immediately)

**Status:** completed

- [x] Define an abstract `LocationSink` adapter interface with a default production implementation connecting to DVT LocationSimulation and a mock test sink capturing emitted coordinates.
- [x] Implement robust spherical geometry math (Haversine distance, destination point projection given start coordinates, bearing in degrees, and distance in meters).
- [x] Implement `POST /move_step` endpoint accepting `{ "direction": "w"|"a"|"s"|"d", "speed_kmh": float }` that calculates the displacement for 1 second (`speed_kmh / 3.6` meters), updates active location, and sends it to the location sink.
- [x] Add automated tests verifying coordinate displacement accuracy for all four cardinal directions (North=0°, South=180°, West=270°, East=90°) and varying speeds using `MockLocationSink`.
