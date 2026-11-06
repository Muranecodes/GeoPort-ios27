"""
Server-side Navigation Controller and Movement Engine.
Ticks at 1.0 Hz in a background worker thread, interpolating polyline coordinates,
updating device location via LocationSink, and managing pause/resume/stop lifecycle.
"""

import logging
import math
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from location_sink import LocationSink

logger = logging.getLogger("GeoPort")

_EARTH_RADIUS_METERS = 6371000.0

_CARDINAL_BEARINGS: Dict[str, float] = {
    "w": 0.0,          # North
    "s": 180.0,        # South
    "a": 270.0,        # West
    "d": 90.0,         # East
    "arrowup": 0.0,
    "arrowdown": 180.0,
    "arrowleft": 270.0,
    "arrowright": 90.0,
    "up": 0.0,
    "down": 180.0,
    "left": 270.0,
    "right": 90.0,
    "north": 0.0,
    "south": 180.0,
    "west": 270.0,
    "east": 90.0,
}


def _validate_speed(speed: Any) -> float:
    """
    Validates and converts a speed value in km/h.
    Must be numeric, finite, and strictly greater than 0.
    """
    try:
        val = float(speed)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid speed value: {speed!r}; expected numeric.") from exc

    if math.isnan(val) or math.isinf(val) or val <= 0:
        raise ValueError("speed_kmh must be a positive number greater than 0.")

    return val


def _validate_coords(lat: Any, lng: Any) -> Tuple[float, float]:
    """
    Validates coordinate numbers and bounds: -90 <= lat <= 90 and -180 <= lng <= 180.
    Raises ValueError if non-numeric, NaN/infinite, or out of range.
    """
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Non-numeric coordinates: lat={lat!r}, lng={lng!r}") from exc
    if math.isnan(lat_f) or math.isinf(lat_f) or math.isnan(lng_f) or math.isinf(lng_f):
        raise ValueError(f"Coordinates cannot be NaN or infinite: ({lat_f}, {lng_f})")
    if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0):
        raise ValueError(
            f"Coordinates out of bounds: ({lat_f}, {lng_f}); expected lat in [-90, 90] and lng in [-180, 180]"
        )
    return lat_f, lng_f


def _get_bearing_for_direction(direction: str) -> float:
    """
    Maps directional keys ('w', 'a', 's', 'd', arrows, cardinal names) to compass bearing degrees.
    """
    key = str(direction).strip().lower()
    if key in _CARDINAL_BEARINGS:
        return _CARDINAL_BEARINGS[key]
    raise ValueError(f"Invalid direction: '{direction}'. Expected one of ['w', 'a', 's', 'd'].")


def _haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculates great-circle distance between two coordinates in meters.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return _EARTH_RADIUS_METERS * c


def _destination_point(
    lat: float, lng: float, bearing_degrees: float, distance_meters: float
) -> Tuple[float, float]:
    """
    Calculates destination coordinates given start point (lat, lng),
    bearing in degrees (0° = North, 90° = East, 180° = South, 270° = West),
    and distance in meters.
    """
    if distance_meters == 0:
        return lat, lng

    phi1 = math.radians(lat)
    lambda1 = math.radians(lng)
    theta = math.radians(bearing_degrees)
    delta = distance_meters / _EARTH_RADIUS_METERS

    sin_phi1 = math.sin(phi1)
    cos_phi1 = math.cos(phi1)
    sin_delta = math.sin(delta)
    cos_delta = math.cos(delta)

    sin_phi2 = sin_phi1 * cos_delta + cos_phi1 * sin_delta * math.cos(theta)
    sin_phi2 = max(-1.0, min(1.0, sin_phi2))
    phi2 = math.asin(sin_phi2)

    y = math.sin(theta) * sin_delta * cos_phi1
    x = cos_delta - sin_phi1 * sin_phi2
    lambda2 = lambda1 + math.atan2(y, x)

    # Normalize longitude to [-180, 180]
    lambda2 = (lambda2 + 3.0 * math.pi) % (2.0 * math.pi) - math.pi

    return math.degrees(phi2), math.degrees(lambda2)


def _calculate_bearing(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculates initial compass bearing in degrees (0° - 360°) from (lat1, lng1) to (lat2, lng2).
    """
    if lat1 == lat2 and lng1 == lng2:
        return 0.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lng2 - lng1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)

    bearing_rad = math.atan2(y, x)
    return (math.degrees(bearing_rad) + 360.0) % 360.0


def _calculate_polyline_distance(waypoints: List[Tuple[float, float]]) -> float:
    """
    Calculates total great-circle distance along polyline waypoints in meters.
    """
    if not waypoints or len(waypoints) < 2:
        return 0.0
    total = 0.0
    for i in range(len(waypoints) - 1):
        total += _haversine_distance(
            float(waypoints[i][0]),
            float(waypoints[i][1]),
            float(waypoints[i + 1][0]),
            float(waypoints[i + 1][1]),
        )
    return total


def _interpolate_polyline(
    waypoints: List[Tuple[float, float]], distance_meters: float
) -> Tuple[float, float]:
    """
    Interpolates a coordinate at distance_meters along the polyline.
    """
    if not waypoints:
        raise ValueError("Waypoints list cannot be empty")
    if len(waypoints) == 1 or distance_meters <= 0:
        return float(waypoints[0][0]), float(waypoints[0][1])

    remaining = float(distance_meters)
    for i in range(len(waypoints) - 1):
        p1 = (float(waypoints[i][0]), float(waypoints[i][1]))
        p2 = (float(waypoints[i + 1][0]), float(waypoints[i + 1][1]))
        seg_dist = _haversine_distance(p1[0], p1[1], p2[0], p2[1])
        if seg_dist <= 0:
            continue
        if remaining <= seg_dist:
            bearing = _calculate_bearing(p1[0], p1[1], p2[0], p2[1])
            return _destination_point(p1[0], p1[1], bearing, remaining)
        remaining -= seg_dist

    return float(waypoints[-1][0]), float(waypoints[-1][1])


class NavigationController:
    """
    Manages 1Hz background navigation along polyline waypoints at a specified speed,
    authoritative location tracking, manual WASD steering, and monotonic anti-burst pacing.
    """

    def __init__(
        self,
        sink: Optional[LocationSink] = None,
        sink_provider: Optional[Callable[[], LocationSink]] = None,
        tick_interval: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        min_step_interval: float = 0.95,
    ) -> None:
        self._sink = sink
        self._sink_provider = sink_provider
        self.tick_interval = tick_interval
        self._clock = clock
        self.min_step_interval = min_step_interval
        self._last_dispatch_time: Optional[float] = None

        self._lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._worker_generation: int = 0
        self._thread: Optional[threading.Thread] = None

        self.waypoints: List[Tuple[float, float]] = []
        self.speed_kmh: float = 5.0
        self.total_distance_m: float = 0.0
        self.traveled_distance_m: float = 0.0
        self.remaining_distance_m: float = 0.0
        self.remaining_time_s: float = 0.0
        self.has_location: bool = False
        self.current_lat: float = 0.0
        self.current_lng: float = 0.0
        self.active: bool = False
        self.paused: bool = False
        self.completed: bool = False

    @property
    def sink(self) -> Optional[LocationSink]:
        if self._sink_provider is not None:
            return self._sink_provider()
        return self._sink

    @sink.setter
    def sink(self, value: Optional[LocationSink]) -> None:
        self._sink = value

    def set_location_coords(self, lat: Any, lng: Any) -> Tuple[float, float]:
        """
        Validates bounds (-90 <= lat <= 90, -180 <= lng <= 180), stores (current_lat, current_lng),
        and sets has_location = True (including when explicitly (0.0, 0.0)).
        Does NOT dispatch to LocationSink and does NOT interrupt active Auto Navigation.
        """
        lat_f, lng_f = _validate_coords(lat, lng)
        with self._lock:
            self.current_lat = lat_f
            self.current_lng = lng_f
            self.has_location = True
            return self.current_lat, self.current_lng

    def get_location_coords(self) -> Optional[Tuple[float, float]]:
        """
        Returns (current_lat, current_lng) if has_location is True, else None.
        """
        with self._lock:
            if not self.has_location:
                return None
            return self.current_lat, self.current_lng

    def _dispatch(self, lat: float, lng: float) -> bool:
        """
        Dispatches coordinates to the active LocationSink (if available),
        logging any exceptions without raising. Returns True on success or no-op, False on failure.
        """
        target_sink = self.sink
        if target_sink is not None:
            try:
                target_sink.set_location(lat, lng)
                return True
            except Exception as e:
                logger.exception("Error dispatching location to sink: %s", e)
                with self._lock:
                    self.paused = True
                    self._last_error = str(e)
                return False
        return True

    def dispatch_current_location(self) -> Tuple[float, float]:
        """
        Raises ValueError("Location is not set") if not has_location;
        otherwise dispatches (current_lat, current_lng) to LocationSink,
        propagating any sink errors, sets _last_dispatch_time = self._clock(),
        and returns (current_lat, current_lng).
        """
        with self._lock:
            if not self.has_location:
                raise ValueError("Location is not set")
            lat, lng = self.current_lat, self.current_lng

        target_sink = self.sink
        if target_sink is not None:
            try:
                target_sink.set_location(lat, lng)
            except Exception as e:
                with self._lock:
                    self._last_error = str(e)
                raise

        with self._lock:
            self._last_dispatch_time = self._clock()
        return lat, lng

    def clear_location(self) -> None:
        """
        Halts any active Auto Navigation and clears simulated coordinates via LocationSink.
        """
        self.stop()
        target_sink = self.sink
        if target_sink is not None:
            target_sink.clear_location()

    def get_speed(self) -> float:
        """
        Returns current speed in km/h.
        """
        with self._lock:
            return self.speed_kmh

    def update_speed(self, speed_kmh: float) -> float:
        """
        Dynamically updates current movement speed and recalculates remaining ETA.
        """
        speed = _validate_speed(speed_kmh)

        with self._lock:
            self.speed_kmh = speed
            speed_mps = speed / 3.6
            if self.active and speed_mps > 0 and self.remaining_distance_m > 0:
                self.remaining_time_s = round(self.remaining_distance_m / speed_mps, 1)
            else:
                self.remaining_time_s = 0.0
            return self.remaining_time_s

    def step_manual(
        self,
        direction: str,
        speed_kmh: Optional[float] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> Dict[str, float]:
        """
        Executes a single 1-second manual steering step in the specified direction.
        - Validates direction against cardinal directions.
        - Resolves speed: uses speed_kmh if provided (without altering self.speed_kmh), else self.speed_kmh.
        - Resolves coordinates: if lat and lng provided, validates bounds and updates authoritative location;
          else if not self.has_location, raises ValueError("Current location is not set").
        - Immediately stops any active Auto Navigation.
        - Enforces monotonic anti-burst pacing (ADR 0001): if time elapsed since _last_dispatch_time < min_step_interval,
          drops the burst displacement and returns {"lat": cur_lat, "lng": cur_lng, "distance_m": 0.0} without dispatching.
        - Otherwise computes 1-second spherical displacement, updates location, sets _last_dispatch_time = clock(),
          dispatches to LocationSink, and returns {"lat": new_lat, "lng": new_lng, "distance_m": distance_meters}.
        """
        if not direction:
            raise ValueError("Direction must be specified.")
        bearing = _get_bearing_for_direction(direction)

        if speed_kmh is not None:
            step_speed = _validate_speed(speed_kmh)
        else:
            with self._lock:
                step_speed = self.speed_kmh

        if lat is not None and lng is not None:
            cur_lat, cur_lng = self.set_location_coords(lat, lng)
        elif lat is not None or lng is not None:
            raise ValueError("Both lat and lng must be provided if overriding coordinates.")
        else:
            with self._lock:
                if not self.has_location:
                    raise ValueError("Current location is not set")
                cur_lat = self.current_lat
                cur_lng = self.current_lng

        # Immediately stop any active Auto Navigation
        self.stop()

        # Anti-burst check (ADR 0001)
        now = self._clock()
        with self._lock:
            prev_dispatch = self._last_dispatch_time
            if prev_dispatch is not None and (now - prev_dispatch) < self.min_step_interval:
                logger.debug(
                    "Dropped manual burst step (%s): elapsed=%.3fs < min_step_interval=%.2fs",
                    direction,
                    now - prev_dispatch,
                    self.min_step_interval,
                )
                return {
                    "lat": self.current_lat,
                    "lng": self.current_lng,
                    "distance_m": 0.0,
                }

        # Compute 1-second spherical displacement using the resolved bearing
        distance_meters = step_speed / 3.6
        new_lat, new_lng = _destination_point(cur_lat, cur_lng, bearing, distance_meters)

        with self._lock:
            self.current_lat = new_lat
            self.current_lng = new_lng
            self.has_location = True
            self._last_dispatch_time = now

        dt_actual = (now - prev_dispatch) if (prev_dispatch is not None and now > prev_dispatch) else 1.0
        eff_kmh = (distance_meters / dt_actual) * 3.6 if dt_actual > 0 else step_speed
        logger.info(
            "Manual step [%s]: (%.6f, %.6f) -> (%.6f, %.6f) | step=%.2fm | dt=%.3fs | speed=%.1f km/h (eff=%.1f km/h)",
            direction,
            cur_lat,
            cur_lng,
            new_lat,
            new_lng,
            distance_meters,
            dt_actual,
            step_speed,
            eff_kmh,
        )

        self._dispatch(new_lat, new_lng)

        return {
            "lat": new_lat,
            "lng": new_lng,
            "distance_m": distance_meters,
        }

    def start(
        self,
        waypoints: List[Union[List[float], Tuple[float, float]]],
        speed_kmh: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Stops any existing navigation, initializes route state, and starts the 1Hz background worker thread.
        """
        with self._lifecycle_lock:
            self.stop()

            if not waypoints or not isinstance(waypoints, list):
                raise ValueError("Waypoints must be a non-empty list of coordinate pairs.")

            clean_pts: List[Tuple[float, float]] = []
            for i, pt in enumerate(waypoints):
                if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                    raise ValueError(f"Waypoint at index {i} is invalid; expected [lat, lng].")
                try:
                    lat = float(pt[0])
                    lng = float(pt[1])
                except (ValueError, TypeError):
                    raise ValueError(f"Waypoint at index {i} contains non-numeric coordinates.")
                if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
                    raise ValueError(f"Waypoint at index {i} coordinates out of bounds: ({lat}, {lng})")
                clean_pts.append((lat, lng))

            if len(clean_pts) < 2:
                raise ValueError("Waypoints must contain at least 2 coordinate pairs.")

            if speed_kmh is None:
                with self._lock:
                    speed = self.speed_kmh
            else:
                speed = _validate_speed(speed_kmh)

            total_dist = _calculate_polyline_distance(clean_pts)
            speed_mps = speed / 3.6
            eta_s = round(total_dist / speed_mps, 1) if speed_mps > 0 else 0.0

            worker_stop_event = threading.Event()
            with self._lock:
                self._worker_generation += 1
                gen_id = self._worker_generation
                self._stop_event.set()
                self._stop_event = worker_stop_event

                self.waypoints = clean_pts
                self.speed_kmh = speed
                self.total_distance_m = total_dist
                self.traveled_distance_m = 0.0
                self.current_lat = clean_pts[0][0]
                self.current_lng = clean_pts[0][1]
                self.has_location = True
                self.remaining_distance_m = total_dist
                self.remaining_time_s = eta_s
                self.active = True
                self.paused = False
                self.completed = False
                now = self._clock()
                if (
                    total_dist > 0
                    and self._last_dispatch_time is not None
                    and (now - self._last_dispatch_time) < self.min_step_interval
                ):
                    should_dispatch_initial = False
                else:
                    self._last_dispatch_time = now
                    should_dispatch_initial = True
                init_lat, init_lng = self.current_lat, self.current_lng

            if total_dist == 0:
                with self._lock:
                    self.active = False
                    self.completed = True
                    self.remaining_distance_m = 0.0
                    self.remaining_time_s = 0.0
                    self._last_dispatch_time = self._clock()
                    worker_stop_event.set()
                self._dispatch(init_lat, init_lng)
                return {
                    "status": "started",
                    "total_distance_m": 0.0,
                    "estimated_duration_s": 0.0,
                }

            logger.info(
                "Navigation start [gen=%d]: (%f, %f) -> (%f, %f) | waypoints=%d | dist=%.1fm | speed=%.1f km/h | eta=%.1fs | initial_dispatch=%s",
                gen_id,
                clean_pts[0][0],
                clean_pts[0][1],
                clean_pts[-1][0],
                clean_pts[-1][1],
                len(clean_pts),
                total_dist,
                speed,
                eta_s,
                should_dispatch_initial,
            )

            if should_dispatch_initial:
                self._dispatch(init_lat, init_lng)

            with self._lock:
                if self._worker_generation == gen_id and self.active and not worker_stop_event.is_set():
                    worker_thread = threading.Thread(
                        target=self._worker_loop,
                        args=(gen_id, worker_stop_event),
                        daemon=True,
                        name=f"GeoPortNavigationWorker-{gen_id}",
                    )
                    self._thread = worker_thread
                    worker_thread.start()

            return {
                "status": "started",
                "total_distance_m": round(total_dist, 1),
                "estimated_duration_s": eta_s,
            }

    def step_tick(
        self,
        dt: Optional[float] = None,
        expected_generation: Optional[int] = None,
    ) -> bool:
        """
        Advances the navigation state by one tick of duration dt (defaults to tick_interval).
        Returns True if navigation remains active, False if completed or stopped.
        """
        step_dt = self.tick_interval if dt is None else float(dt)

        with self._lock:
            if expected_generation is not None and self._worker_generation != expected_generation:
                return False

            if not self.active or self.completed or self.paused:
                return self.active

            now = self._clock()
            if (
                expected_generation is not None
                and self.tick_interval >= self.min_step_interval
                and self._last_dispatch_time is not None
                and (now - self._last_dispatch_time) < self.min_step_interval
            ):
                logger.warning(
                    "Dropped burst navigation tick [gen=%s]: elapsed=%.3fs < min_step_interval=%.2fs",
                    expected_generation,
                    now - self._last_dispatch_time,
                    self.min_step_interval,
                )
                return self.active

            prev_lat, prev_lng = self.current_lat, self.current_lng
            prev_traveled = self.traveled_distance_m
            prev_dispatch = self._last_dispatch_time
            current_speed = self.speed_kmh

            step_distance = (self.speed_kmh / 3.6) * step_dt
            self.traveled_distance_m += step_distance

            if self.traveled_distance_m >= self.total_distance_m:
                self.traveled_distance_m = self.total_distance_m
                self.current_lat, self.current_lng = self.waypoints[-1]
                self.has_location = True
                self.remaining_distance_m = 0.0
                self.remaining_time_s = 0.0
                self.active = False
                self.completed = True
                target_lat, target_lng = self.current_lat, self.current_lng
                finished = True
            else:
                self.current_lat, self.current_lng = _interpolate_polyline(
                    self.waypoints, self.traveled_distance_m
                )
                self.has_location = True
                self.remaining_distance_m = max(
                    0.0, self.total_distance_m - self.traveled_distance_m
                )
                speed_mps = self.speed_kmh / 3.6
                self.remaining_time_s = (
                    round(self.remaining_distance_m / speed_mps, 1)
                    if speed_mps > 0
                    else 0.0
                )
                target_lat, target_lng = self.current_lat, self.current_lng
                finished = False

            rem_dist = self.remaining_distance_m
            self._last_dispatch_time = now

        actual_dist = _haversine_distance(prev_lat, prev_lng, target_lat, target_lng)
        dt_actual = (now - prev_dispatch) if (prev_dispatch is not None and now > prev_dispatch) else step_dt
        eff_kmh = (actual_dist / dt_actual) * 3.6 if dt_actual > 0 else current_speed
        logger.info(
            "Nav tick [gen=%s]: (%.6f, %.6f) -> (%.6f, %.6f) | step=%.2fm | dt=%.3fs | speed=%.1f km/h (eff=%.1f km/h) | rem=%.1fm",
            expected_generation if expected_generation is not None else "direct",
            prev_lat,
            prev_lng,
            target_lat,
            target_lng,
            actual_dist,
            dt_actual,
            current_speed,
            eff_kmh,
            rem_dist,
        )

        success = self._dispatch(target_lat, target_lng)
        if not success:
            with self._lock:
                self.current_lat = prev_lat
                self.current_lng = prev_lng
                self.traveled_distance_m = prev_traveled
                self.remaining_distance_m = max(0.0, self.total_distance_m - prev_traveled)
                self.paused = True
            return False

        if finished:
            self._stop_event.set()

        return not finished

    def _worker_loop(
        self,
        gen_id: Optional[int] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Background worker thread running at 1Hz (tick_interval) with strict monotonic clock
        pacing, per-generation isolation, and anti-burst protection until stopped or completed.
        """
        ev = stop_event if stop_event is not None else self._stop_event
        with self._lock:
            now_init = self._clock()
            if self._last_dispatch_time is not None and self._last_dispatch_time > (now_init - self.tick_interval):
                next_tick_time = max(
                    now_init + self.tick_interval,
                    self._last_dispatch_time + self.tick_interval,
                )
            else:
                next_tick_time = now_init + self.tick_interval

        while not ev.is_set():
            if gen_id is not None and self._worker_generation != gen_id:
                break

            now = self._clock()
            sleep_time = next_tick_time - now
            if sleep_time > 0:
                interrupted = ev.wait(timeout=sleep_time)
                if interrupted or ev.is_set():
                    break
            else:
                # If execution lagged, resync next_tick_time to avoid rapid catch-up bursts
                next_tick_time = self._clock()

            if gen_id is not None and self._worker_generation != gen_id:
                break

            if self.paused:
                next_tick_time = self._clock() + self.tick_interval
                continue

            active = self.step_tick(self.tick_interval, expected_generation=gen_id)
            if not active:
                break

            # Advance next tick time; if behind current time, anchor to now + tick_interval
            next_tick_time += self.tick_interval
            if next_tick_time < self._clock():
                next_tick_time = self._clock() + self.tick_interval

    def stop(self) -> Dict[str, float]:
        """
        Halts the background worker and marks navigation as inactive.
        Returns the last reported coordinate dict: {"lat": ..., "lng": ...}.
        """
        with self._lock:
            was_active = self.active
            self.active = False
            self._worker_generation += 1
            self._stop_event.set()
            thread_to_join = self._thread
            self._thread = None
            lat = self.current_lat
            lng = self.current_lng

        if was_active:
            logger.info("Navigation stopped at (%.6f, %.6f)", lat, lng)

        if thread_to_join is not None and thread_to_join.is_alive():
            if threading.current_thread() != thread_to_join:
                thread_to_join.join(timeout=2.0)

        return {"lat": lat, "lng": lng}

    def pause(self) -> None:
        """
        Pauses movement ticker without stopping worker or clearing route.
        """
        with self._lock:
            if self.active and not self.completed:
                self.paused = True

    def resume(self) -> None:
        """
        Resumes paused movement ticker.
        """
        with self._lock:
            if self.active and not self.completed:
                self.paused = False

    def get_status(self) -> Dict[str, Any]:
        """
        Returns snapshot of current navigation state.
        """
        with self._lock:
            return {
                "active": self.active,
                "paused": self.paused,
                "current_lat": self.current_lat if self.has_location else 0.0,
                "current_lng": self.current_lng if self.has_location else 0.0,
                "speed_kmh": self.speed_kmh,
                "remaining_distance_m": round(self.remaining_distance_m, 1),
                "remaining_time_s": round(self.remaining_time_s, 1),
                "completed": self.completed,
            }
