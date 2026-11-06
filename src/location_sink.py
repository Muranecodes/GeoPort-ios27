"""
Location Sink Adapter Interface and Implementations.
Isolates device communication (DVT / pymobiledevice3) from movement calculation logic.
"""

from abc import ABC, abstractmethod
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging
import queue
import threading
from typing import Any, AsyncIterator, Callable, List, Optional, Tuple

logger = logging.getLogger("GeoPort")


def is_major_version_17_or_greater(version_string: Optional[str]) -> bool:
    """
    Returns True if the major Device iOS Version is 17 or greater.
    """
    if not version_string:
        return False
    try:
        major_version = int(str(version_string).split(".")[0])
        return major_version >= 17
    except (ValueError, IndexError):
        return False


@dataclass(frozen=True)
class DeviceSessionContext:
    """
    Immutable snapshot of the active connected iOS device context for DvtLocationSink.
    """

    udid: Optional[str] = None
    ios_version: Optional[str] = None
    connection_type: Optional[str] = None
    rsd_host: Optional[str] = None
    rsd_port: Optional[int] = None
    lockdown: Optional[Any] = None
    has_rsd_session: bool = True


@asynccontextmanager
async def _default_simulation_session(ctx: DeviceSessionContext) -> AsyncIterator[Any]:
    """
    Default pymobiledevice3 context manager yielding a LocationSimulation instance
    for either iOS 17+ (RSD) or iOS <17 (Lockdown).
    """
    from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
    from pymobiledevice3.services.dvt.dvt_secure_socket_proxy import DvtSecureSocketProxyService
    from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation

    if is_major_version_17_or_greater(ctx.ios_version):
        if not ctx.rsd_host or not ctx.rsd_port:
            raise RuntimeError("RSD tunnel is not ready")
        async with RemoteServiceDiscoveryService((ctx.rsd_host, int(ctx.rsd_port))) as sp_rsd:
            with DvtSecureSocketProxyService(sp_rsd) as dvt:
                yield LocationSimulation(dvt)
    else:
        if ctx.lockdown is None:
            raise RuntimeError("Lockdown session is not ready")
        with DvtSecureSocketProxyService(lockdown=ctx.lockdown) as dvt:
            yield LocationSimulation(dvt)


class LocationSink(ABC):
    """
    Abstract adapter at the Location Sink seam for dispatching or clearing simulated coordinates.
    """

    @abstractmethod
    def set_location(self, latitude: float, longitude: float) -> None:
        """
        Dispatches coordinates (latitude, longitude) to the target device or test recorder.
        """
        raise NotImplementedError

    def clear_location(self) -> None:
        """
        Clears the simulated location and restores hardware GPS on the target device.
        """
        pass


class MockLocationSink(LocationSink):
    """
    In-memory Location Sink adapter capturing dispatched coordinates for unit and integration testing.
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
    Deep production Location Sink adapter owning the iOS DVT LocationSimulation session lifecycle:
    - Routes iOS 27+ (when modern_controller is enabled) to ModernLocationController.
    - Manages persistent DVT streaming worker thread and ack queue for iOS 17–26 (RSD) and iOS <17 (Lockdown).
    - Automatically restarts the streaming session if the target device or tunnel signature changes.
    - Clears simulated location in-place on an active streaming session or via a one-shot DVT session.
    """

    def __init__(
        self,
        context_provider: Optional[Callable[[], DeviceSessionContext]] = None,
        modern_controller: Optional[Any] = None,
        image_mounter: Optional[Callable[[], Any]] = None,
        simulation_session_factory: Optional[Callable[[DeviceSessionContext], Any]] = None,
        startup_timeout: float = 30.0,
        stream_timeout: float = 5.0,
    ) -> None:
        self._context_provider = context_provider
        self._modern_controller = modern_controller
        self._image_mounter = image_mounter
        self._session_factory = simulation_session_factory or _default_simulation_session
        self._startup_timeout = startup_timeout
        self._stream_timeout = stream_timeout

        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event: Optional[threading.Event] = None
        self._command_queue: Optional[queue.Queue] = None
        self._active_signature: Optional[Tuple[Any, ...]] = None

    def _get_context(self) -> DeviceSessionContext:
        if self._context_provider is not None:
            return self._context_provider()
        return DeviceSessionContext()

    def _is_modern_ios27(self, ctx: DeviceSessionContext) -> bool:
        return bool(
            ctx.ios_version
            and is_major_version_17_or_greater(ctx.ios_version)
            and self._modern_controller is not None
            and getattr(self._modern_controller, "enabled", False)
            and str(ctx.ios_version).startswith("27.")
        )

    @staticmethod
    def _build_signature(ctx: DeviceSessionContext) -> Tuple[Any, ...]:
        if is_major_version_17_or_greater(ctx.ios_version):
            return (
                "rsd",
                ctx.udid,
                ctx.connection_type,
                ctx.ios_version,
                ctx.rsd_host,
                int(ctx.rsd_port) if ctx.rsd_port is not None else None,
            )
        return (
            "lockdown",
            ctx.udid,
            ctx.connection_type,
            ctx.ios_version,
            id(ctx.lockdown) if ctx.lockdown is not None else None,
        )

    def _is_stream_alive(self) -> bool:
        return (
            self._thread is not None
            and self._thread.is_alive()
            and self._stop_event is not None
            and not self._stop_event.is_set()
            and self._command_queue is not None
        )

    def set_location(self, latitude: float, longitude: float) -> None:
        ctx = self._get_context()
        if not ctx.ios_version:
            raise ValueError("No iOS version present")

        with self._lock:
            if self._is_modern_ios27(ctx):
                self._stop_stream_thread()
                self._modern_controller.set(ctx.udid, latitude, longitude)
                return

            if not ctx.has_rsd_session:
                raise RuntimeError("Selected device has no RSD session")

            is_v17_plus = is_major_version_17_or_greater(ctx.ios_version)
            if is_v17_plus:
                if not ctx.rsd_host or not ctx.rsd_port:
                    raise RuntimeError("RSD tunnel is not ready")
            else:
                if self._image_mounter is not None:
                    self._image_mounter()

            sig = self._build_signature(ctx)

            # Reuse active persistent DVT session if healthy and bound to the same device/tunnel signature
            if self._is_stream_alive() and self._active_signature == sig:
                ack: queue.Queue = queue.Queue(maxsize=1)
                self._command_queue.put(("set", (latitude, longitude), ack))
                try:
                    failure = ack.get(timeout=self._stream_timeout)
                    if failure is None:
                        return
                    logger.warning(
                        "Active DVT session coordinate update failed: %s; restarting session",
                        failure,
                    )
                except queue.Empty:
                    logger.warning("Active DVT session update timed out; restarting session")

            self._start_stream_thread(ctx, sig, latitude, longitude)

    def _start_stream_thread(
        self,
        ctx: DeviceSessionContext,
        sig: Tuple[Any, ...],
        latitude: float,
        longitude: float,
    ) -> None:
        self._stop_stream_thread()

        stop_event = threading.Event()
        cmd_queue: queue.Queue = queue.Queue()
        startup_result: queue.Queue = queue.Queue(maxsize=1)
        is_v17_plus = is_major_version_17_or_greater(ctx.ios_version)

        async def _stream_loop() -> None:
            async with self._session_factory(ctx) as sim:
                if not is_v17_plus:
                    sim.clear()
                sim.set(latitude, longitude)
                startup_result.put_nowait(None)
                logger.warning("LocationSimulation accepted the set call")

                while not stop_event.is_set():
                    try:
                        item = cmd_queue.get_nowait()
                    except queue.Empty:
                        item = None

                    if item is not None:
                        action, payload, ack_queue = item
                        try:
                            if action == "set":
                                sim.set(payload[0], payload[1])
                                logger.debug(
                                    "Persistent DVT streamed location to (%s, %s)",
                                    payload[0],
                                    payload[1],
                                )
                                if ack_queue is not None:
                                    ack_queue.put_nowait(None)
                            elif action == "clear":
                                sim.clear()
                                logger.warning("Location Cleared Successfully")
                                if ack_queue is not None:
                                    ack_queue.put_nowait(None)
                                stop_event.set()
                                break
                        except Exception as exc:
                            logger.exception("Error in persistent DVT stream command (%s)", action)
                            if ack_queue is not None:
                                ack_queue.put_nowait(exc)
                            raise

                    await asyncio.sleep(0.05)

        def _worker() -> None:
            try:
                asyncio.run(_stream_loop())
            except ConnectionResetError as cre:
                if "[Errno 54] Connection reset by peer" in str(cre):
                    logger.error(
                        "The Set Location buffer is full. Try to 'Stop Location' to clear old connections"
                    )
                if startup_result.empty():
                    startup_result.put_nowait(cre)
            except Exception as exc:
                logger.exception("Error setting location in DVT stream worker")
                if startup_result.empty():
                    startup_result.put_nowait(exc)
            finally:
                with self._lock:
                    if self._command_queue is cmd_queue:
                        self._command_queue = None
                        self._active_signature = None

        worker_thread = threading.Thread(target=_worker, daemon=True)
        self._stop_event = stop_event
        self._command_queue = cmd_queue
        self._active_signature = sig
        self._thread = worker_thread
        worker_thread.start()

        try:
            failure = startup_result.get(timeout=self._startup_timeout)
        except queue.Empty as exc:
            self._stop_stream_thread()
            raise TimeoutError(
                f"LocationSimulation did not respond within {int(self._startup_timeout)} seconds"
            ) from exc

        if failure is not None:
            self._stop_stream_thread()
            raise failure

    def _stop_stream_thread(self) -> None:
        with self._lock:
            stop_event = self._stop_event
            thread = self._thread
            self._stop_event = None
            self._thread = None
            self._command_queue = None
            self._active_signature = None

        if stop_event is not None:
            stop_event.set()
        if thread is not None and thread.is_alive():
            if threading.current_thread() != thread:
                thread.join(timeout=1.0)

    def clear_location(self) -> None:
        ctx = self._get_context()

        with self._lock:
            if self._is_modern_ios27(ctx):
                self._stop_stream_thread()
                self._modern_controller.clear(ctx.udid)
                return

            # If an active persistent DVT stream is open, clear directly on that session first
            if self._is_stream_alive() and self._command_queue is not None:
                ack: queue.Queue = queue.Queue(maxsize=1)
                self._command_queue.put(("clear", None, ack))
                cleared_in_stream = False
                stream_error: Optional[Exception] = None
                try:
                    result = ack.get(timeout=self._stream_timeout)
                    if result is None:
                        cleared_in_stream = True
                    elif isinstance(result, Exception):
                        stream_error = result
                except queue.Empty:
                    logger.warning("Timed out clearing location on active DVT stream; falling back")

                self._stop_stream_thread()
                if cleared_in_stream:
                    return
                if stream_error is not None:
                    logger.warning("In-stream clear failed (%s); attempting one-shot clear", stream_error)

            self._stop_stream_thread()

            if not ctx.ios_version or not ctx.has_rsd_session:
                return

            if is_major_version_17_or_greater(ctx.ios_version):
                if not ctx.rsd_host or not ctx.rsd_port:
                    return
            else:
                if ctx.lockdown is None:
                    return

            async def _one_shot_clear() -> None:
                async with self._session_factory(ctx) as sim:
                    sim.clear()
                    logger.warning("Location Cleared Successfully")

            asyncio.run(_one_shot_clear())
