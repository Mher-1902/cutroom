import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch, MagicMock

from cutroom import launcher


class LauncherTests(unittest.TestCase):
    def test_refuses_to_stop_an_unrelated_process(self):
        result = subprocess.CompletedProcess([], 0, stdout="/usr/bin/python3 unrelated.py\n")
        with patch.object(launcher.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "identity"):
                launcher.verified_pid({"pid": 1234})

    def test_refuses_to_stop_unmanaged_legacy_launch(self):
        with self.assertRaisesRegex(RuntimeError, "original terminal"):
            launcher.verified_pid({"legacy_launch": True})

    def test_refuses_another_installation_on_same_port(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"app": "Cutroom", "installation": "another-installation"}).encode()
        with patch.object(launcher.urllib.request, "urlopen", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "Another Cutroom"):
                launcher.probe()

    def test_identity_uses_this_installation(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"app": "Cutroom", "pid": 1234,
             "installation": hashlib.sha256(str(launcher.ROOT).encode()).hexdigest()}).encode()
        with patch.object(launcher.urllib.request, "urlopen", return_value=response):
            self.assertEqual(launcher.probe()["pid"], 1234)

    def test_port_conflict_does_not_load_project_state(self):
        import app
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(app, "ROOT", Path(folder)), patch("sys.argv", ["app.py", "--no-browser"]), \
                 patch.object(app, "ThreadingHTTPServer", side_effect=OSError("in use")), \
                 patch.object(app, "Studio") as studio:
                app.main()
                studio.assert_not_called()
