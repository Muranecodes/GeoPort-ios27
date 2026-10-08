import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src is in python path
src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from modern_location_client import ModernLocationController


class TestModernLocationControllerUnit(unittest.TestCase):
    def test_enabled_property(self):
        ctrl_empty = ModernLocationController()
        self.assertFalse(ctrl_empty.enabled)

        ctrl_py = ModernLocationController(python_executable="python.exe")
        self.assertTrue(ctrl_py.enabled)

        ctrl_bridge = ModernLocationController(bridge_executable="bridge.exe")
        self.assertTrue(ctrl_bridge.enabled)

    def test_command_generation(self):
        ctrl = ModernLocationController(python_executable="C:/test/python.exe")
        cmd = ctrl._command("set", "00008101-0001", 25.033, 121.565)
        self.assertEqual(cmd[0], "C:/test/python.exe")
        self.assertEqual(cmd[2], "set")
        self.assertIn("--udid", cmd)
        self.assertIn("00008101-0001", cmd)
        self.assertIn("25.033", cmd)
        self.assertIn("121.565", cmd)


class TestModernLocationControllerStreaming(unittest.TestCase):
    def setUp(self):
        self.mock_bridge_code = """
import sys
import json

action = sys.argv[1] if len(sys.argv) > 1 else "set"
if action == "clear":
    sys.stdout.write(json.dumps({"cleared": True}) + "\\n")
    sys.stdout.flush()
    sys.exit(0)

sys.stdout.write(json.dumps({"ready": True}) + "\\n")
sys.stdout.flush()

for line in sys.stdin:
    line = line.strip()
    if not line:
        break
    try:
        cmd = json.loads(line)
        if cmd.get("action") == "set":
            sys.stdout.write(json.dumps({"ready": True, "lat": cmd.get("latitude"), "lng": cmd.get("longitude")}) + "\\n")
            sys.stdout.flush()
        elif cmd.get("action") == "clear":
            sys.stdout.write(json.dumps({"cleared": True}) + "\\n")
            sys.stdout.flush()
            break
    except Exception as exc:
        sys.stdout.write(json.dumps({"error": str(exc)}) + "\\n")
        sys.stdout.flush()
"""
        self.bridge_script_path = Path(__file__).resolve().parent / "_test_dummy_bridge.py"
        self.bridge_script_path.write_text(self.mock_bridge_code, encoding="utf-8")

    def tearDown(self):
        if self.bridge_script_path.exists():
            try:
                self.bridge_script_path.unlink()
            except OSError:
                pass

    def test_persistent_streaming_across_multiple_steps(self):
        ctrl = ModernLocationController(python_executable=sys.executable)
        ctrl.bridge = self.bridge_script_path

        udid = "test-udid-12345"
        # First step: spawns bridge process
        ctrl.set(udid, 25.0001, 121.0001)
        initial_proc = ctrl._process
        self.assertIsNotNone(initial_proc)
        self.assertIsNone(initial_proc.poll())

        # Second step: MUST reuse same process without restarting or clearing
        ctrl.set(udid, 25.0002, 121.0002)
        self.assertIs(ctrl._process, initial_proc)
        self.assertIsNone(ctrl._process.poll())

        # Third step: MUST reuse same process again
        ctrl.set(udid, 25.0003, 121.0003)
        self.assertIs(ctrl._process, initial_proc)
        self.assertIsNone(ctrl._process.poll())

        # Stop controller: cleans up process
        ctrl.stop()
        self.assertIsNone(ctrl._process)
        initial_proc.wait(timeout=5)
        self.assertIsNotNone(initial_proc.poll())

    def test_switching_udid_restarts_session(self):
        ctrl = ModernLocationController(python_executable=sys.executable)
        ctrl.bridge = self.bridge_script_path

        ctrl.set("device-a", 25.0, 121.0)
        proc_a = ctrl._process
        self.assertIsNotNone(proc_a)

        ctrl.set("device-b", 25.1, 121.1)
        proc_b = ctrl._process
        self.assertIsNotNone(proc_b)
        self.assertIsNot(proc_a, proc_b)

        ctrl.stop()

    def test_clear_delegates_to_stop_when_active(self):
        ctrl = ModernLocationController(python_executable=sys.executable)
        ctrl.bridge = self.bridge_script_path

        ctrl.set("device-target", 10.0, 20.0)
        proc = ctrl._process
        self.assertIsNotNone(proc)

        ctrl.clear("device-target")
        self.assertIsNone(ctrl._process)
        proc.wait(timeout=5)
        self.assertIsNotNone(proc.poll())


if __name__ == "__main__":
    unittest.main()
