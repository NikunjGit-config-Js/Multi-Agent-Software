from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStatus(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    RUNNING = "running"
    INTEGRATING = "integrating"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, Enum):
    BLOCKED = "blocked"
    READY = "ready"
    DELEGATING = "delegating"
    RUNNING = "running"
    REVIEWING = "reviewing"
    REVISING = "revising"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class MissionRequest:
    objective: str
    deliverables: list[str]
    provider: str = "demo"
    quality_threshold: float = 0.78
    max_parallel: int = 4
    context: str = ""

    def validate(self) -> None:
        self.objective = self.objective.strip()
        self.context = self.context.strip()
        self.deliverables = list(dict.fromkeys(self.deliverables))
        if len(self.objective) < 12:
            raise ValueError("Objective must be at least 12 characters long")
        allowed = {"research", "code", "ux", "notes", "slides"}
        unknown = set(self.deliverables) - allowed
        if not self.deliverables or unknown:
            raise ValueError(f"Choose one or more valid deliverables; unknown: {sorted(unknown)}")
        if self.provider not in {"demo", "openai", "anthropic"}:
            raise ValueError("Provider must be demo, openai, or anthropic")
        if not 0.5 <= self.quality_threshold <= 1.0:
            raise ValueError("Quality threshold must be between 0.5 and 1.0")
        if not 1 <= self.max_parallel <= 8:
            raise ValueError("max_parallel must be between 1 and 8")


@dataclass(slots=True)
class TaskSpec:
    id: str
    title: str
    department: str
    agent: str
    brief: str
    deliverable: str
    manager: str = "Department Manager"
    manager_directive: str = ""
    dependencies: list[str] = field(default_factory=list)
    status: str = TaskStatus.BLOCKED.value
    progress: int = 0
    revision: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    quality_score: float | None = None
    review_summary: str = ""
    artifact_id: str | None = None
    error: str | None = None


@dataclass(slots=True)
class Artifact:
    id: str
    task_id: str
    title: str
    kind: str
    content: str
    filename: str
    created_at: str = field(default_factory=utc_now)
    quality_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Event:
    id: int
    at: str
    kind: str
    actor: str
    message: str
    task_id: str | None = None


@dataclass(slots=True)
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


@dataclass(slots=True)
class RunState:
    id: str
    request: MissionRequest
    status: str = RunStatus.QUEUED.value
    phase: str = "Mission received"
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    completed_at: str | None = None
    tasks: list[TaskSpec] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    progress: int = 0
    error: str | None = None
    bundle_artifact_id: str | None = None

    def to_dict(self, include_content: bool = True) -> dict[str, Any]:
        data = asdict(self)
        if not include_content:
            for artifact in data["artifacts"]:
                artifact.pop("content", None)
        return data
