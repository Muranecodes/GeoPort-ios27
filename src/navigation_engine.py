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

from geometry import (
    calculate_polyline_distance,
    calculate_step,
    destination_point,
    get_bearing_for_direction,
    interpolate_polyline,
    validate_speed,
)
from location_sink import LocationSink

logger = logging.getLogger("GeoPort")


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


class NavigationController:
    """
    Manages 1Hz background navigation along polyline waypoints at a specified speed,
    authoritative location tracking, manual WASD steering, and monotonic anti-burst pacing.
    """

    def __init__(
        self,
        sink: Optional[LocationSink] = None,
        sink_provider: Optional[Callable[[], LocationSink]] = None,
        on_location_update: Optional[Callable[[float, float], None]] = None,
        tick_interval: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        min_step_interval: float = 0.95,
    ) -> None:
        self._sink = sink
        self._sink_provider = sink_provider
        self.on_location_update = on_location_update
        self.tick_interval = tick_interval
        self._clock = clock
        self.min_step_interval = min_step_interval
        self._last_dispatch_time: Optional[float] = None

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
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

    def dispatch_current_location(self) -> Tuple[float, float]:
        """
        Raises ValueError("Location is not set") if not has_location;
        otherwise dispatches (current_lat, current_lng) to LocationSink,
        sets _last_dispatch_time = self._clock(), and returns (current_lat, current_lng).
        """
        with self._lock:
            if not self.has_location:
                raise ValueError("Location is not set")
            lat, lng = self.current_lat, self.current_lng
            self._last_dispatch_time = self._clock()

        target_sink = self.sink
        if target_sink is not None:
            try:
                target_sink.set_location(lat, lng)
            except Exception as e:
                logger.exception("Error dispatching current location to sink: %s", e)

        if self.on_location_update is not None:
            try:
                self.on_location_update(lat, lng)
            except Exception as e:
                logger.exception("Error calling on_location_update: %s", e)

        return lat, lng

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
        speed = validate_speed(speed_kmh)

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
          dispatches to LocationSink and on_location_update, and returns {"lat": new_lat, "lng": new_lng, "distance_m": distance_meters}.
        """
        if not direction:
            raise ValueError("Direction must be specified.")
        # Validates direction against cardinal directions via get_bearing_for_direction
        get_bearing_for_direction(direction)

        if speed_kmh is not None:
            step_speed = validate_speed(speed_kmh)
        else:
            with self._lock:
                step_speed = self.speed_kmh

        if lat is not None and lng is not None:
            cur_lat, cur_lng = _validate_coords(lat, lng)
            with self._lock:
                self.current_lat = cur_lat
                self.current_lng = cur_lng
                self.has_location = True
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
            if self._last_dispatch_time is not None and (now - self._last_dispatch_time) < self.min_step_interval:
                return {
                    "lat": self.current_lat,
                    "lng": self.current_lng,
                    "distance_m": 0.0,
                }

        # Compute 1-second spherical displacement
        new_lat, new_lng, distance_meters = calculate_step(
            cur_lat, cur_lng, direction, step_speed, duration_seconds=1.0
        )

        with self._lock:
            self.current_lat = new_lat
            self.current_lng = new_lng
            self.has_location = True
            self._last_dispatch_time = now

        target_sink = self.sink
        if target_sink is not None:
            try:
                target_sink.set_location(new_lat, new_lng)
            except Exception as e:
                logger.exception("Error dispatching manual step to sink: %s", e)

        if self.on_location_update is not None:
            try:
                self.on_location_update(new_lat, new_lng)
            except Exception as e:
                logger.exception("Error calling on_location_update: %s", e)

        return {
            "lat": new_lat,
            "lng": new_lng,
            "distance_m": distance_meters,
        }

    def start(
        self,
        waypoints: List[Union[List[float], Tuple[float, float]]],
        speed_kmh: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Stops any existing navigation, initializes route state, and starts the 1Hz background worker thread.
        """
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

        speed = validate_speed(speed_kmh)

        total_dist = calculate_polyline_distance(clean_pts)
        speed_mps = speed / 3.6
        eta_s = round(total_dist / speed_mps, 1) if speed_mps > 0 else 0.0

        with self._lock:
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
            self._stop_event.clear()
            self._last_dispatch_time = self._clock()

        if total_dist == 0:
            with self._lock:
                self.active = False
                self.completed = True
                self.remaining_distance_m = 0.0
                self.remaining_time_s = 0.0
            target_sink = self.sink
            if target_sink is not None:
                try:
                    target_sink.set_location(self.current_lat, self.current_lng)
                except Exception as e:
                    logger.exception("Error setting initial sink location: %s", e)
            if self.on_location_update is not None:
                try:
                    self.on_location_update(self.current_lat, self.current_lng)
                except Exception as e:
                    logger.exception("Error calling on_location_update: %s", e)
            return {
                "status": "started",
                "total_distance_m": 0.0,
                "estimated_duration_s": 0.0,
            }

        target_sink = self.sink
        if target_sink is not None:
            try:
                target_sink.set_location(self.current_lat, self.current_lng)
            except Exception as e:
                logger.exception("Error setting initial sink location: %s", e)
        if self.on_location_update is not None:
            try:
                self.on_location_update(self.current_lat, self.current_lng)
            except Exception as e:
                logger.exception("Error calling on_location_update: %s", e)

        self._thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="GeoPortNavigationWorker"
        )
        self._thread.start()

        return {
            "status": "started",
            "total_distance_m": round(total_dist, 1),
            "estimated_duration_s": eta_s,
        }

    def step_tick(self, dt: Optional[float] = None) -> bool:
        """
        Advances the navigation state by one tick of duration dt (defaults to tick_interval).
        Returns True if navigation remains active, False if completed or stopped.
        """
        step_dt = self.tick_interval if dt is None else float(dt)

        with self._lock:
            if not self.active or self.completed or self.paused:
                return self.active

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
                self._stop_event.set()
                target_lat, target_lng = self.current_lat, self.current_lng
                finished = True
            else:
                self.current_lat, self.current_lng = interpolate_polyline(
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

            self._last_dispatch_time = self._clock()

        target_sink = self.sink
        if target_sink is not None:
            try:
                target_sink.set_location(target_lat, target_lng)
            except Exception as e:
                logger.exception("Error dispatching location in navigation tick: %s", e)

        if self.on_location_update is not None:
            try:
                self.on_location_update(target_lat, target_lng)
            except Exception as e:
                logger.exception("Error in navigation on_location_update: %s", e)

        return not finished

    def _worker_loop(self) -> None:
        """
        Background worker thread running at 1Hz (tick_interval) with strict monotonic clock
        pacing and anti-burst protection until stopped or completed.
        """
        next_tick_time = self._clock() + self.tick_interval
        while not self._stop_event.is_set():
            now = self._clock()
            sleep_time = next_tick_time - now
            if sleep_time > 0:
                interrupted = self._stop_event.wait(timeout=sleep_time)
                if interrupted or self._stop_event.is_set():
                    break
            else:
                # If execution lagged, resync next_tick_time to avoid rapid catch-up bursts
                next_tick_time = self._clock()

            if self.paused:
                next_tick_time = self._clock() + self.tick_interval
                continue

            active = self.step_tick(self.tick_interval)
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
            self.active = False
            self._stop_event.set()
            lat = self.current_lat
            lng = self.current_lng

        if self._thread is not None and self._thread.is_alive():
            if threading.current_thread() != self._thread:
                self._thread.join(timeout=2.0)
            self._thread = None

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
                "has_location": self.has_location,
            }
