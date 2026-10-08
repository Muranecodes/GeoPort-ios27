"""
Location Sink Adapter Interface and Implementations.
Isolates device communication (DVT / pymobiledevice3) from movement calculation logic.
"""

from abc import ABC, abstractmethod
from typing import Callable, List, Optional, Tuple
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
    """

    def __init__(
        self,
        dispatch_fn: Optional[Callable[[float, float], None]] = None,
        clear_fn: Optional[Callable[[], None]] = None,
    ) -> None:
        self._dispatch_fn = dispatch_fn
        self._clear_fn = clear_fn

    def set_location(self, latitude: float, longitude: float) -> None:
        if self._dispatch_fn is not None:
            self._dispatch_fn(latitude, longitude)
            return

        try:
            import main

            if hasattr(main, "dispatch_dvt_location"):
                main.dispatch_dvt_location(latitude, longitude)
            elif hasattr(main, "start_set_location_thread"):
                main.start_set_location_thread(latitude, longitude)
            else:
                logger.warning(
                    "No DVT dispatch implementation found when setting (%s, %s)",
                    latitude,
                    longitude,
                )
        except Exception as e:
            logger.exception("DvtLocationSink failed to dispatch location")
            raise

    def clear_location(self) -> None:
        if self._clear_fn is not None:
            self._clear_fn()
            return

        try:
            import main

            if hasattr(main, "stop_set_location_thread"):
                main.stop_set_location_thread()
        except Exception as e:
            logger.exception("DvtLocationSink failed to clear location")
            raise
