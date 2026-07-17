from __future__ import annotations

import json
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .models import (
    Artifact,
    Event,
    MissionRequest,
    RunState,
    RunStatus,
    TaskSpec,
    TaskStatus,
    utc_now,
)
from .planner import CapabilityPlanner
from .providers import ModelProvider, ProviderResponse, build_provider
from .providers.base import extract_json
from .storage import RunStore


class Orchestrator:
    def __init__(self, store: RunStore) -> None:
        self.store = store
        self.planner = CapabilityPlanner()
        self._lock = threading.RLock()

    def start(self, request: MissionRequest) -> RunState:
        request.validate()
        run = RunState(id=f"run_{uuid.uuid4().hex[:10]}", request=request)
        self._event(run, "mission", "Chief of Staff", "Mission accepted and queued for the CEO.")
        self.store.register(run)
        thread = threading.Thread(target=self._run, args=(run,), daemon=True)
        thread.start()
        return run

    def run_sync(self, request: MissionRequest) -> RunState:
        request.validate()
        run = RunState(id=f"run_{uuid.uuid4().hex[:10]}", request=request)
        self._event(run, "mission", "Chief of Staff", "Mission accepted and queued for the CEO.")
        self.store.register(run)
        self._run(run)
        return run

    def _run(self, run: RunState) -> None:
        try:
            provider = build_provider(run.request.provider)
            self._set_phase(run, RunStatus.PLANNING.value, "CEO is composing the workforce", 4)
            self._event(run, "planning", "CEO Agent", "Reading the objective and selecting departments.")
            tasks, plan_usage = self.planner.plan(run.request, provider)
            self._record_usage(run, plan_usage)
            with self._lock:
                run.tasks = tasks
                run.started_at = utc_now()
                run.status = RunStatus.RUNNING.value
                run.phase = "Departments are executing"
                run.progress = 10
                self.store.save(run)
            departments = ", ".join(task.department for task in tasks)
            self._event(run, "delegation", "CEO Agent", f"Workforce deployed: {departments}.")
            self._execute_graph(run, provider)
            self._integrate(run, provider)
            with self._lock:
                run.status = RunStatus.COMPLETED.value
                run.phase = "Delivery ready"
                run.progress = 100
                run.completed_at = utc_now()
                self.store.save(run)
            self._event(run, "completed", "Integration Executive", "Mission complete. Delivery bundle is ready.")
        except Exception as exc:
            with self._lock:
                run.status = RunStatus.FAILED.value
                run.phase = "Mission stopped safely"
                run.error = _safe_error(exc)
                run.completed_at = utc_now()
                self.store.save(run)
            self._event(run, "failed", "Chief of Staff", f"Mission stopped: {run.error}")

    def _execute_graph(self, run: RunState, provider: ModelProvider) -> None:
        while True:
            with self._lock:
                unfinished = [
                    task
                    for task in run.tasks
                    if task.status not in {TaskStatus.COMPLETED.value, TaskStatus.FAILED.value}
                ]
                if not unfinished:
                    break
                completed_ids = {
                    task.id for task in run.tasks if task.status == TaskStatus.COMPLETED.value
                }
                failed_ids = {task.id for task in run.tasks if task.status == TaskStatus.FAILED.value}
                if any(set(task.dependencies) & failed_ids for task in unfinished):
                    raise RuntimeError("A required upstream department failed")
                ready = [task for task in unfinished if set(task.dependencies) <= completed_ids]
                for task in ready:
                    task.status = TaskStatus.READY.value
                self.store.save(run)
            if not ready:
                raise RuntimeError("Task graph is blocked or cyclic")

            worker_count = min(run.request.max_parallel, len(ready))
            errors: list[Exception] = []
            with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="orgmind") as pool:
                futures = {pool.submit(self._execute_task, run, task, provider): task for task in ready}
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as exc:
                        task = futures[future]
                        with self._lock:
                            task.status = TaskStatus.FAILED.value
                            task.error = _safe_error(exc)
                            task.completed_at = utc_now()
                            self.store.save(run)
                        self._event(run, "failed", task.agent, f"{task.title} failed: {task.error}", task.id)
                        errors.append(exc)
            if errors:
                raise RuntimeError(f"{len(errors)} department task(s) failed")

    def _execute_task(
        self,
        run: RunState,
        task: TaskSpec,
        provider: ModelProvider,
    ) -> None:
        with self._lock:
            task.status = TaskStatus.DELEGATING.value
            task.progress = 8
            task.started_at = utc_now()
            self.store.save(run)
        self._event(run, "manager", task.manager, f"Preparing the work order for {task.agent}.", task.id)

        dependencies = self._dependency_context(run, task)
        manager_response = provider.complete(
            role="manager",
            system=(
                "ORGMIND_ROLE:MANAGE\n"
                f"You are {task.manager}, accountable for {task.department}. Turn the CEO brief "
                "into a short, bounded work order for one specialist. Define 3-5 checks. Do not "
                "produce the final artifact and do not add scope."
            ),
            prompt=(
                f"[OBJECTIVE]\n{run.request.objective}\n"
                f"[DELIVERABLE]\n{task.deliverable}\n"
                f"[CEO_BRIEF]\n{task.brief}\n"
                f"[UPSTREAM_WORK]\n{dependencies or 'None'}"
            ),
        )
        self._record_usage(run, manager_response)
        with self._lock:
            task.manager_directive = manager_response.text.strip()[:4000]
            task.status = TaskStatus.RUNNING.value
            task.progress = 20
            self.store.save(run)
        self._event(run, "started", task.manager, f"Delegated {task.title} to {task.agent}.", task.id)

        response = provider.complete(
            role="worker",
            system=(
                "ORGMIND_ROLE:EXECUTE\n"
                f"You are the {task.agent} in {task.department}. Produce only the requested "
                "artifact. Be concrete, label assumptions, never invent verification or sources, "
                "and do not claim to have performed external actions. Use clean Markdown."
            ),
            prompt=self._worker_prompt(run, task, dependencies),
        )
        self._record_usage(run, response)
        content = response.text.strip()
        if not content:
            raise RuntimeError("Worker returned an empty artifact")
        with self._lock:
            task.status = TaskStatus.REVIEWING.value
            task.progress = 68
            self.store.save(run)
        self._event(run, "review", "Quality Auditor", f"Reviewing {task.title}.", task.id)

        review = self._review(run, task, content, provider)
        score = review["score"]
        if score < run.request.quality_threshold:
            with self._lock:
                task.status = TaskStatus.REVISING.value
                task.progress = 78
                task.revision = 1
                self.store.save(run)
            self._event(
                run,
                "revision",
                "Quality Auditor",
                f"Returned to {task.agent}: {review['feedback']}",
                task.id,
            )
            revision_response = provider.complete(
                role="worker",
                system=(
                    "ORGMIND_ROLE:REVISE\n"
                    f"You are the {task.agent}. Revise the artifact once using the QA feedback. "
                    "Return the full replacement artifact in Markdown."
                ),
                prompt=(
                    self._worker_prompt(run, task, dependencies)
                    + f"\n[QA_FEEDBACK]\n{review['feedback']}\n[CURRENT_ARTIFACT]\n{content}"
                ),
            )
            self._record_usage(run, revision_response)
            content = revision_response.text.strip() or content
            review = self._review(run, task, content, provider)
            score = review["score"]

        artifact = Artifact(
            id=f"artifact_{uuid.uuid4().hex[:10]}",
            task_id=task.id,
            title=task.title,
            kind=task.deliverable,
            content=content,
            filename=f"{task.deliverable}.md",
            quality_score=score,
            metadata={
                "department": task.department,
                "agent": task.agent,
                "provider": provider.name,
                "revision": task.revision,
            },
        )
        with self._lock:
            run.artifacts.append(artifact)
            task.artifact_id = artifact.id
            task.quality_score = score
            task.review_summary = review["summary"]
            task.status = TaskStatus.COMPLETED.value
            task.progress = 100
            task.completed_at = utc_now()
            completed = sum(t.status == TaskStatus.COMPLETED.value for t in run.tasks)
            run.progress = 10 + int(78 * completed / max(1, len(run.tasks)))
            self.store.save(run)
        verdict = "accepted" if score >= run.request.quality_threshold else "accepted with QA caveat"
        self._event(
            run,
            "accepted",
            "Quality Auditor",
            f"{task.title} {verdict} at {score:.0%} quality.",
            task.id,
        )

    def _review(
        self,
        run: RunState,
        task: TaskSpec,
        content: str,
        provider: ModelProvider,
    ) -> dict[str, object]:
        response = provider.complete(
            role="reviewer",
            system=(
                "ORGMIND_ROLE:REVIEW\n"
                "You are an independent QA auditor. Return JSON only: "
                '{"score":0.0,"summary":"...","feedback":"...","passed":false}. '
                "Score completeness, specificity, internal consistency, safety, and fit to brief."
            ),
            prompt=(
                f"[OBJECTIVE]\n{run.request.objective}\n"
                f"[DELIVERABLE]\n{task.deliverable}\n"
                f"[BRIEF]\n{task.brief}\n"
                f"[REVISION]\n{task.revision}\n"
                f"[ARTIFACT]\n{content[:18000]}"
            ),
            json_mode=True,
        )
        self._record_usage(run, response)
        try:
            payload = extract_json(response.text)
            score = min(1.0, max(0.0, float(payload.get("score", 0.0))))
            return {
                "score": score,
                "summary": str(payload.get("summary") or "QA review completed.")[:500],
                "feedback": str(payload.get("feedback") or "Improve specificity and completeness.")[:1000],
            }
        except Exception:
            return {
                "score": 0.65,
                "summary": "Reviewer response could not be parsed reliably.",
                "feedback": "Make the artifact explicit, complete, and aligned with the brief.",
            }

    def _integrate(self, run: RunState, provider: ModelProvider) -> None:
        self._set_phase(run, RunStatus.INTEGRATING.value, "Integration office is packaging delivery", 92)
        self._event(run, "integration", "Integration Executive", "Checking cross-artifact coherence.")
        artifact_digest = "\n\n".join(
            f"## {artifact.title}\n{artifact.content[:6000]}" for artifact in run.artifacts
        )
        response = provider.complete(
            role="integrator",
            system=(
                "ORGMIND_ROLE:INTEGRATE\n"
                "You are the integration executive. Write a brief executive synthesis and a "
                "concrete next decision. Do not repeat every artifact and do not invent facts."
            ),
            prompt=f"[OBJECTIVE]\n{run.request.objective}\n[ARTIFACTS]\n{artifact_digest}",
        )
        self._record_usage(run, response)

        manifest_payload = {
            "run_id": run.id,
            "objective": run.request.objective,
            "provider": run.request.provider,
            "quality_threshold": run.request.quality_threshold,
            "artifacts": [
                {
                    "id": artifact.id,
                    "filename": artifact.filename,
                    "kind": artifact.kind,
                    "quality_score": artifact.quality_score,
                    "agent": artifact.metadata.get("agent"),
                }
                for artifact in run.artifacts
            ],
        }
        manifest = Artifact(
            id=f"artifact_{uuid.uuid4().hex[:10]}",
            task_id="integration",
            title="Delivery manifest",
            kind="manifest",
            content=json.dumps(manifest_payload, indent=2),
            filename="manifest.json",
            metadata={"agent": "Integration Executive", "provider": "deterministic"},
        )
        bundle_sections = [
            "# OrgMind Final Delivery",
            f"**Mission:** {run.request.objective}",
            response.text.strip(),
            "---",
            "## Quality register\n\n"
            + "\n".join(
                f"- **{task.title}:** {(task.quality_score or 0):.0%} — {task.review_summary}"
                for task in run.tasks
            ),
        ]
        for artifact in run.artifacts:
            bundle_sections.extend(["---", artifact.content])
        bundle = Artifact(
            id=f"artifact_{uuid.uuid4().hex[:10]}",
            task_id="integration",
            title="Final delivery bundle",
            kind="bundle",
            content="\n\n".join(bundle_sections).strip() + "\n",
            filename="FINAL_DELIVERY.md",
            metadata={"agent": "Integration Executive", "provider": provider.name},
        )
        with self._lock:
            run.artifacts.extend([manifest, bundle])
            run.bundle_artifact_id = bundle.id
            run.progress = 98
            self.store.save(run)

    def _worker_prompt(self, run: RunState, task: TaskSpec, dependencies: str) -> str:
        return (
            f"[OBJECTIVE]\n{run.request.objective}\n"
            f"[DELIVERABLE]\n{task.deliverable}\n"
            f"[BRIEF]\n{task.brief}\n"
            f"[MANAGER_WORK_ORDER]\n{task.manager_directive or task.brief}\n"
            f"[USER_CONTEXT]\n{run.request.context or 'No additional context supplied.'}\n"
            f"[UPSTREAM_WORK]\n{dependencies or 'No upstream artifact; work directly from the mission.'}"
        )

    def _dependency_context(self, run: RunState, task: TaskSpec) -> str:
        with self._lock:
            artifact_ids = {
                candidate.artifact_id
                for candidate in run.tasks
                if candidate.id in task.dependencies and candidate.artifact_id
            }
            chunks = [
                f"### {artifact.title}\n{artifact.content[:7000]}"
                for artifact in run.artifacts
                if artifact.id in artifact_ids
            ]
        return "\n\n".join(chunks)

    def _record_usage(self, run: RunState, response: ProviderResponse) -> None:
        with self._lock:
            run.usage.calls += 1
            run.usage.input_tokens += response.input_tokens
            run.usage.output_tokens += response.output_tokens
            run.usage.estimated_cost_usd += response.estimated_cost_usd
            self.store.save(run)

    def _set_phase(self, run: RunState, status: str, phase: str, progress: int) -> None:
        with self._lock:
            run.status = status
            run.phase = phase
            run.progress = progress
            self.store.save(run)

    def _event(
        self,
        run: RunState,
        kind: str,
        actor: str,
        message: str,
        task_id: str | None = None,
    ) -> None:
        with self._lock:
            run.events.append(
                Event(
                    id=len(run.events) + 1,
                    at=utc_now(),
                    kind=kind,
                    actor=actor,
                    message=message,
                    task_id=task_id,
                )
            )
            self.store.save(run)


def _safe_error(exc: Exception) -> str:
    message = re.sub(r"\s+", " ", str(exc)).strip()
    return (message or exc.__class__.__name__)[:500]
