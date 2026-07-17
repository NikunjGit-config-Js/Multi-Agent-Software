import unittest

from orgmind.models import MissionRequest
from orgmind.planner import CapabilityPlanner
from orgmind.providers.demo import DemoProvider


class PlannerTests(unittest.TestCase):
    def test_dependencies_are_bounded_and_acyclic(self):
        request = MissionRequest(
            objective="Design an accountable multi-agent product for project work.",
            deliverables=["research", "code", "ux", "notes", "slides"],
        )
        request.validate()
        tasks, _ = CapabilityPlanner().plan(request, DemoProvider())
        by_id = {task.id: task for task in tasks}
        self.assertEqual(len(tasks), 5)
        self.assertEqual(by_id["task_research"].dependencies, [])
        self.assertEqual(by_id["task_code"].dependencies, [])
        self.assertEqual(by_id["task_notes"].dependencies, ["task_research"])
        self.assertEqual(
            set(by_id["task_slides"].dependencies),
            {"task_research", "task_code", "task_ux", "task_notes"},
        )

    def test_slides_alone_has_no_dependency(self):
        request = MissionRequest(
            objective="Create an executive narrative for a responsible AI product.",
            deliverables=["slides"],
        )
        request.validate()
        tasks, _ = CapabilityPlanner().plan(request, DemoProvider())
        self.assertEqual(tasks[0].dependencies, [])


if __name__ == "__main__":
    unittest.main()

