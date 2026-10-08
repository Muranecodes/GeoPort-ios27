"""Run current pymobiledevice3 beside GeoPort's bundled legacy dependency."""

import json
import logging
import queue
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger("GeoPort")


class ModernLocationController:
    def __init__(self, python_executable=None, bridge_executable=None):
        self.python_executable = python_executable
        self.bridge_executable = bridge_executable
        self.bridge = Path(__file__).with_name("modern_location_bridge.py")
        self._process = None
        self._udid = None
        self._response_queue = None
        self._lock = threading.RLock()

    @property
    def enabled(self):
        return bool(self.python_executable or self.bridge_executable)

    def _command(self, action, udid, *coordinates):
        if self.bridge_executable:
            command = [self.bridge_executable]
        elif self.python_executable:
            command = [self.python_executable, str(self.bridge)]
        else:
            raise RuntimeError("No modern pymobiledevice3 location bridge configured")
        return [*command, action, "--udid", udid,
                *(str(value) for value in coordinates)]

    def _clear(self, udid):
        result = subprocess.run(self._command("clear", udid), capture_output=True,
                                text=True, timeout=45)
        if result.returncode:
            raise RuntimeError(result.stdout.strip() or result.stderr.strip() or
                               "DVT clear failed")

    def set(self, udid, latitude, longitude):
        with self._lock:
            # Check if active bridge process is already alive for this udid
            if (
                self._process is not None
                and self._process.poll() is None
                and self._udid == udid
                and self._response_queue is not None
            ):
                try:
                    cmd = json.dumps({
                        "action": "set",
                        "latitude": float(latitude),
                        "longitude": float(longitude),
                    })
                    self._process.stdin.write(cmd + "\n")
                    self._process.stdin.flush()

                    try:
                        line = self._response_queue.get(timeout=10)
                    except queue.Empty as exc:
                        raise TimeoutError("DVT stream set did not respond within 10 seconds") from exc

                    if not line:
                        raise RuntimeError("DVT bridge stream closed unexpectedly")

                    response = json.loads(line)
                    if not response.get("ready"):
                        raise RuntimeError(response.get("error") or "DVT stream set failed")
                    return
                except Exception as exc:
                    logger.warning("Error streaming to active DVT session: %s; restarting bridge", exc)
                    self.stop()

            # Otherwise, spawn a new bridge process
            self.stop()
            process = subprocess.Popen(
                self._command("set", udid, latitude, longitude),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1,
            )
            response_queue = queue.Queue()

            def _reader():
                try:
                    for line in iter(process.stdout.readline, ''):
                        response_queue.put(line)
                except Exception:
                    pass
                response_queue.put('')

            reader_thread = threading.Thread(target=_reader, daemon=True)
            reader_thread.start()

            try:
                try:
                    line = response_queue.get(timeout=90)
                except queue.Empty as exc:
                    raise TimeoutError("DVT set did not respond within 90 seconds") from exc

                if not line:
                    stderr_content = process.stderr.read().strip() if process.stderr else ""
                    raise RuntimeError(stderr_content or "DVT set process exited without response")

                response = json.loads(line)
                if not response.get("ready"):
                    stderr_content = process.stderr.read().strip() if process.stderr else ""
                    raise RuntimeError(response.get("error") or stderr_content or "DVT set failed")
            except Exception:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                for stream in (process.stdin, process.stdout, process.stderr):
                    try:
                        if stream:
                            stream.close()
                    except Exception:
                        pass
                raise

            self._process = process
            self._udid = udid
            self._response_queue = response_queue

    def stop(self):
        with self._lock:
            process, udid = self._process, self._udid
            self._process = self._udid = self._response_queue = None
            if process is None:
                return
            if process.poll() is None:
                try:
                    process.stdin.write(json.dumps({"action": "clear"}) + "\n")
                    process.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass
                try:
                    process.wait(timeout=10)
                except (subprocess.TimeoutExpired, OSError):
                    process.kill()
                    process.wait()
            for stream in (process.stdin, process.stdout, process.stderr):
                try:
                    if stream:
                        stream.close()
                except Exception:
                    pass
            if process.returncode != 0 and process.returncode is not None:
                self._clear(udid)

    def clear(self, udid):
        with self._lock:
            if self._process is not None and self._udid == udid:
                self.stop()
            else:
                self._clear(udid)
