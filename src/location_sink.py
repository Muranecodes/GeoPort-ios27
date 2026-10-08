"""
Location Sink Adapter Interface and Implementations.
Isolates device communication (DVT / pymobiledevice3) from movement calculation logic.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional, Tuple
import logging

logger = logging.getLogger("GeoPort")


class LocationSink(ABC):
    """
    Abstract adapter for dispatching simulated locations to target devices.
    """

    @abstractmethod
    def set_location(self, latitude: float, longitude: float) -> None:
        """
        Dispatches coordinates (latitude, longitude) to the device or test recorder.
        """
        raise NotImplementedError

    def clear_location(self) -> None:
        """
        Clears the simulated location and returns device to hardware GPS.
        """
        pass


class MockLocationSink(LocationSink):
    """
    In-memory mock location sink capturing dispatched coordinates for unit and integration testing.
    """

    def __init__(self) -> None:
        self.locations: List[Tuple[float, float]] = []
        self.cleared: bool = False

    def set_location(self, latitude: float, longitude: float) -> None:
        self.locations.append((latitude, longitude))

    def clear_location(self) -> None:
        self.cleared = True

    @property
    def last_location(self) -> Optional[Tuple[float, float]]:
        return self.locations[-1] if self.locations else None

    @property
    def call_count(self) -> int:
        return len(self.locations)

    def reset(self) -> None:
        self.locations.clear()
        self.cleared = False


class DvtLocationSink(LocationSink):
    """
    Production location sink connecting to Apple DVT LocationSimulation or delegating handler.
    Supports clean callback injection and optional persistent streaming queue.
    """

    def __init__(
        self,
        dispatch_fn: Optional[Callable[[float, float], None]] = None,
        clear_fn: Optional[Callable[[], None]] = None,
        session_queue: Optional[Any] = None,
    ) -> None:
        self._dispatch_fn = dispatch_fn
        self._clear_fn = clear_fn
        self._session_queue = session_queue

    @property
    def session_queue(self) -> Optional[Any]:
        return self._session_queue

    @session_queue.setter
    def session_queue(self, queue_obj: Optional[Any]) -> None:
        self._session_queue = queue_obj

    def set_location(self, latitude: float, longitude: float) -> None:
        if self._session_queue is not None:
            self._session_queue.put((latitude, longitude))
            return

        if self._dispatch_fn is not None:
            self._dispatch_fn(latitude, longitude)
            return

        logger.warning(
            "No DVT dispatch implementation found when setting (%s, %s)",
            latitude,
            longitude,
        )

    def clear_location(self) -> None:
        if self._clear_fn is not None:
            self._clear_fn()
            return

        logger.warning("No DVT clear handler configured")

