from __future__ import annotations

from .models import MissionRequest, TaskSpec, TaskStatus
from .providers.base import ModelProvider, ProviderResponse, extract_json


CAPABILITIES = {
    "research": {
        "title": "Research the problem space",
        "department": "Strategy & Research",
        "agent": "Research Lead",
        "manager": "Strategy Director",
        "brief": "Frame the problem, surface assumptions, define evidence needs, risks, and measurable success criteria.",
    },
    "code": {
        "title": "Design the implementation",
        "department": "Engineering",
        "agent": "Principal Engineer",
        "manager": "VP Engineering",
        "brief": "Produce a safe, modular implementation blueprint with interfaces, pseudocode or code, and acceptance tests.",
    },
    "ux": {
        "title": "Specify the user experience",
        "department": "Product Design",
        "agent": "Product Designer",
        "manager": "Product Director",
        "brief": "Turn the objective into a clear user journey, interface structure, states, trust signals, and accessibility requirements.",
    },
    "notes": {
        "title": "Create learning notes",
        "department": "Knowledge Office",
        "agent": "Learning Editor",
        "manager": "Knowledge Director",
        "brief": "Explain the core ideas concisely, preserve the reasoning, and add practical self-check questions.",
    },
    "slides": {
        "title": "Build the presentation narrative",
        "department": "Executive Communications",
        "agent": "Presentation Director",
        "manager": "Chief Communications Officer",
        "brief": "Create a boardroom-ready story with one message per slide, suggested visuals, metrics, and a decisive next step.",
    },
}


class CapabilityPlanner:
    def plan(
        self,
        request: MissionRequest,
        provider: ModelProvider,
    ) -> tuple[list[TaskSpec], ProviderResponse]:
        response = provider.complete(
            role="ceo",
            system=(
                "ORGMIND_ROLE:PLAN\n"
                "You are the CEO planner of a bounded AI organization. Refine task titles and "
                "briefs without adding deliverables. Return JSON: "
                '{"tasks":[{"deliverable":"research","title":"...","brief":"..."}]}. '
                "Do not assign external actions or claim that evidence has been verified."
            ),
            prompt=(
                f"Objective: {request.objective}\n"
                f"Requested deliverables: {', '.join(request.deliverables)}\n"
                f"Additional context: {request.context or 'None'}"
            ),
            json_mode=True,
        )
        refinements: dict[str, dict[str, str]] = {}
        try:
            payload = extract_json(response.text)
            for item in payload.get("tasks", []):
                kind = str(item.get("deliverable", "")).strip().lower()
                if kind in request.deliverables:
                    refinements[kind] = {
                        "title": str(item.get("title", "")).strip(),
                        "brief": str(item.get("brief", "")).strip(),
                    }
        except Exception:
            # A deterministic graph is the safe fallback; provider prose must not
            # be allowed to create an unbounded or cyclic workflow.
            refinements = {}

        tasks: list[TaskSpec] = []
        selected = set(request.deliverables)
        for kind in request.deliverables:
            capability = CAPABILITIES[kind]
            dependencies: list[str] = []
            if kind == "notes" and "research" in selected:
                dependencies = ["task_research"]
            elif kind == "slides":
                dependencies = [f"task_{item}" for item in request.deliverables if item != "slides"]
            refinement = refinements.get(kind, {})
            title = refinement.get("title") or capability["title"]
            brief = refinement.get("brief") or capability["brief"]
            tasks.append(
                TaskSpec(
                    id=f"task_{kind}",
                    title=title[:100],
                    department=capability["department"],
                    agent=capability["agent"],
                    brief=brief[:700],
                    deliverable=kind,
                    manager=capability["manager"],
                    dependencies=dependencies,
                    status=TaskStatus.BLOCKED.value if dependencies else TaskStatus.READY.value,
                )
            )
        return tasks, response
