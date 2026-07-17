import json
import tempfile
import unittest
from pathlib import Path

from orgmind.models import MissionRequest
from orgmind.orchestrator import Orchestrator
from orgmind.storage import RunStore


class OrchestratorTests(unittest.TestCase):
    def test_end_to_end_demo_workforce(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            run = Orchestrator(store).run_sync(
                MissionRequest(
                    objective="Build a corporate AI workforce that creates coordinated project deliverables.",
                    deliverables=["research", "code", "ux", "notes", "slides"],
                    provider="demo",
                    quality_threshold=0.78,
                )
            )
            self.assertEqual(run.status, "completed")
            self.assertEqual(run.progress, 100)
            self.assertTrue(all(task.status == "completed" for task in run.tasks))
            self.assertEqual(len(run.artifacts), 7)
            self.assertIsNotNone(run.bundle_artifact_id)
            slides = next(task for task in run.tasks if task.deliverable == "slides")
            self.assertEqual(slides.revision, 1)
            self.assertGreaterEqual(slides.quality_score, 0.78)
            bundle = next(item for item in run.artifacts if item.kind == "bundle")
            self.assertIn("OrgMind Final Delivery", bundle.content)
            self.assertIn("Quality register", bundle.content)
            self.assertGreater(run.usage.calls, 10)

            saved = Path(directory, f"{run.id}.json")
            self.assertTrue(saved.is_file())
            payload = json.loads(saved.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "completed")

    def test_saved_run_can_be_reloaded(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RunStore(directory)
            run = Orchestrator(store).run_sync(
                MissionRequest(
                    objective="Produce concise learning notes for bounded AI task graphs.",
                    deliverables=["notes"],
                )
            )
            reloaded = RunStore(directory).get(run.id)
            self.assertIsNotNone(reloaded)
            self.assertEqual(reloaded.status, "completed")
            self.assertEqual(reloaded.artifacts[-1].kind, "bundle")


if __name__ == "__main__":
    unittest.main()

