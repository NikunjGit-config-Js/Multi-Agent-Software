import unittest

from orgmind.models import MissionRequest


class MissionRequestTests(unittest.TestCase):
    def test_valid_request_is_normalized(self):
        request = MissionRequest(
            objective="  Build a useful AI workflow for students.  ",
            deliverables=["research", "code", "research"],
        )
        request.validate()
        self.assertEqual(request.objective, "Build a useful AI workflow for students.")
        self.assertEqual(request.deliverables, ["research", "code"])

    def test_rejects_unknown_deliverable(self):
        request = MissionRequest(
            objective="Build a useful AI workflow for students.",
            deliverables=["telepathy"],
        )
        with self.assertRaises(ValueError):
            request.validate()

    def test_rejects_unbounded_parallelism(self):
        request = MissionRequest(
            objective="Build a useful AI workflow for students.",
            deliverables=["research"],
            max_parallel=50,
        )
        with self.assertRaises(ValueError):
            request.validate()

    def test_accepts_gemini_provider(self):
        request = MissionRequest(
            objective="Build a useful AI workflow for students.",
            deliverables=["research"],
            provider="gemini",
        )
        request.validate()
        self.assertEqual(request.provider, "gemini")


if __name__ == "__main__":
    unittest.main()
