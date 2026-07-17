from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from .models import Artifact, Event, MissionRequest, RunState, TaskSpec, Usage


class RunStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._runs: dict[str, RunState] = {}
        self._load_existing()

    def register(self, run: RunState) -> None:
        with self._lock:
            self._runs[run.id] = run
            self._write(run)

    def save(self, run: RunState) -> None:
        with self._lock:
            self._runs[run.id] = run
            self._write(run)

    def get(self, run_id: str) -> RunState | None:
        with self._lock:
            return self._runs.get(run_id)

    def snapshot(self, run_id: str, *, include_content: bool = False) -> dict[str, Any] | None:
        with self._lock:
            run = self._runs.get(run_id)
            return run.to_dict(include_content=include_content) if run else None

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            runs = sorted(self._runs.values(), key=lambda run: run.created_at, reverse=True)[:limit]
            return [
                {
                    "id": run.id,
                    "objective": run.request.objective,
                    "status": run.status,
                    "progress": run.progress,
                    "created_at": run.created_at,
                    "completed_at": run.completed_at,
                    "artifact_count": len(run.artifacts),
                }
                for run in runs
            ]

    def _write(self, run: RunState) -> None:
        target = self.root / f"{run.id}.json"
        temporary = self.root / f".{run.id}.tmp"
        temporary.write_text(
            json.dumps(run.to_dict(include_content=True), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temporary, target)

    def _load_existing(self) -> None:
        for path in sorted(self.root.glob("run_*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                run = _run_from_dict(payload)
                self._runs[run.id] = run
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                continue


def _run_from_dict(data: dict[str, Any]) -> RunState:
    return RunState(
        id=data["id"],
        request=MissionRequest(**data["request"]),
        status=data.get("status", "failed"),
        phase=data.get("phase", "Recovered run"),
        created_at=data.get("created_at", ""),
        started_at=data.get("started_at"),
        completed_at=data.get("completed_at"),
        tasks=[TaskSpec(**item) for item in data.get("tasks", [])],
        artifacts=[Artifact(**item) for item in data.get("artifacts", [])],
        events=[Event(**item) for item in data.get("events", [])],
        usage=Usage(**data.get("usage", {})),
        progress=int(data.get("progress", 0)),
        error=data.get("error"),
        bundle_artifact_id=data.get("bundle_artifact_id"),
    )

