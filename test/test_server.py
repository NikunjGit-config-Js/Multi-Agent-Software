import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from orgmind.server import OrgMindApp


class ServerTests(unittest.TestCase):
    def test_health_and_mission_api(self):
        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            previous = os.environ.get("ORGMIND_DATA_DIR")
            os.environ["ORGMIND_DATA_DIR"] = directory
            try:
                app = OrgMindApp(project_root)
                server = ThreadingHTTPServer(("127.0.0.1", 0), app.handler_class())
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{server.server_port}"

                health = self._get_json(f"{base}/api/health")
                self.assertTrue(health["ok"])
                self.assertTrue(health["providers"]["demo"]["ready"])

                body = json.dumps(
                    {
                        "objective": "Design a reliable AI workforce for technical project delivery.",
                        "deliverables": ["research", "slides"],
                        "provider": "demo",
                    }
                ).encode("utf-8")
                request = urllib.request.Request(
                    f"{base}/api/runs",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    created = json.loads(response.read())
                run_id = created["run_id"]
                run = {}
                for _ in range(80):
                    run = self._get_json(f"{base}/api/runs/{run_id}")
                    if run["status"] in {"completed", "failed"}:
                        break
                    time.sleep(0.05)
                self.assertEqual(run["status"], "completed")
                with urllib.request.urlopen(f"{base}/api/runs/{run_id}/bundle", timeout=5) as response:
                    bundle = response.read().decode("utf-8")
                self.assertIn("OrgMind Final Delivery", bundle)
            finally:
                if "server" in locals():
                    server.shutdown()
                    server.server_close()
                if previous is None:
                    os.environ.pop("ORGMIND_DATA_DIR", None)
                else:
                    os.environ["ORGMIND_DATA_DIR"] = previous

    @staticmethod
    def _get_json(url):
        with urllib.request.urlopen(url, timeout=5) as response:
            return json.loads(response.read())


if __name__ == "__main__":
    unittest.main()

