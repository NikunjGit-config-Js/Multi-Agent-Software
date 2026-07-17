from __future__ import annotations

import json
import re

from .base import ModelProvider, ProviderResponse


class DemoProvider(ModelProvider):
    """Deterministic local workforce used for onboarding and tests."""

    name = "demo"

    def complete(
        self,
        *,
        role: str,
        system: str,
        prompt: str,
        json_mode: bool = False,
    ) -> ProviderResponse:
        marker = _marker(system)
        if marker == "PLAN":
            text = json.dumps({"message": "Deterministic capability plan accepted."})
        elif marker == "MANAGE":
            text = self._manage(prompt)
        elif marker == "REVIEW":
            text = self._review(prompt)
        elif marker == "REVISE":
            text = self._execute(prompt, revised=True)
        elif marker == "INTEGRATE":
            text = self._integrate(prompt)
        else:
            text = self._execute(prompt, revised=False)
        return ProviderResponse(
            text=text,
            model="orgmind-demo-1",
            input_tokens=max(1, len(prompt) // 4),
            output_tokens=max(1, len(text) // 4),
            estimated_cost_usd=0.0,
        )

    def _manage(self, prompt: str) -> str:
        deliverable = (_section(prompt, "DELIVERABLE") or "research").lower()
        checklists = {
            "research": [
                "Separate known inputs from assumptions.",
                "Define the decision the research must unlock.",
                "Include measurable success criteria and risks.",
            ],
            "code": [
                "Define module boundaries before implementation details.",
                "Use safe defaults and explicit failure behaviour.",
                "Include acceptance tests and operational boundaries.",
            ],
            "ux": [
                "Start from the primary user journey.",
                "Specify empty, active, review, complete, and failure states.",
                "Make trust, accessibility, and control visible.",
            ],
            "notes": [
                "Preserve only the concepts required for recall.",
                "Explain trade-offs in plain language.",
                "End with self-check questions and a one-line summary.",
            ],
            "slides": [
                "Build one narrative from problem to next decision.",
                "Keep one core message per slide and suggest a visual.",
                "Carry forward metrics and caveats from upstream work.",
            ],
        }
        items = checklists.get(deliverable, checklists["research"])
        return "Manager work order:\n" + "\n".join(
            f"{index + 1}. {item}" for index, item in enumerate(items)
        )

    def _execute(self, prompt: str, revised: bool) -> str:
        objective = _section(prompt, "OBJECTIVE") or "the stated mission"
        deliverable = (_section(prompt, "DELIVERABLE") or "research").lower()
        suffix = "\n\n## Revision record\nQA feedback incorporated; scope, checks, and ownership are now explicit." if revised else ""
        generators = {
            "research": _research,
            "code": _code,
            "ux": _ux,
            "notes": _notes,
            "slides": _slides,
        }
        content = generators.get(deliverable, _research)(objective)
        return content + suffix

    def _review(self, prompt: str) -> str:
        deliverable = (_section(prompt, "DELIVERABLE") or "research").lower()
        revision = int(_section(prompt, "REVISION") or "0")
        base = {"research": 0.84, "code": 0.82, "ux": 0.85, "notes": 0.88, "slides": 0.74}.get(deliverable, 0.80)
        score = min(0.96, base + revision * 0.14)
        strengths = {
            "research": "Clear assumptions, decision criteria, and risk framing.",
            "code": "Bounded modules, safe defaults, and testable interfaces.",
            "ux": "Strong information hierarchy and actionable states.",
            "notes": "Concise learning path with checks for understanding.",
            "slides": "Coherent narrative with one message per slide.",
        }.get(deliverable, "The artifact follows its requested contract.")
        improvement = (
            "Make success metrics and the final call-to-action more explicit."
            if score < 0.78
            else "Add real domain evidence before production use."
        )
        return json.dumps(
            {
                "score": round(score, 2),
                "summary": strengths,
                "feedback": improvement,
                "passed": score >= 0.78,
            }
        )

    def _integrate(self, prompt: str) -> str:
        objective = _section(prompt, "OBJECTIVE") or "the mission"
        return (
            "## Executive synthesis\n\n"
            f"The workforce completed a coordinated delivery for **{objective}**. "
            "The package separates evidence, implementation, experience design, learning, "
            "and communication so each artifact can evolve without breaking the others.\n\n"
            "### Recommended next decision\n\n"
            "Validate the riskiest assumption with one real user or stakeholder, then turn "
            "the accepted code blueprint into a thin vertical prototype."
        )


def _marker(system: str) -> str:
    match = re.search(r"ORGMIND_ROLE:([A-Z]+)", system)
    return match.group(1) if match else "EXECUTE"


def _section(prompt: str, name: str) -> str:
    pattern = rf"\[{re.escape(name)}\]\s*(.*?)(?=\n\[[A-Z_]+\]|\Z)"
    match = re.search(pattern, prompt, flags=re.DOTALL)
    return match.group(1).strip() if match else ""


def _short(objective: str) -> str:
    return objective.strip().rstrip(".")[:240]


def _research(objective: str) -> str:
    return f"""# Research & Strategy Memo

## Mission

{_short(objective)}.

## Executive finding

The strongest MVP is a narrow, observable workflow that solves one valuable user journey end to end. The team should prove coordination quality before increasing the number of agents or integrations.

## Problem framing

- **Primary user:** the person accountable for turning an ambiguous objective into finished work.
- **Pain:** sequential tool switching loses context, duplicates effort, and hides responsibility.
- **Job to be done:** delegate a mission once, monitor the work, intervene at decision gates, and receive traceable artifacts.
- **Non-goal:** unrestricted autonomous access to external systems.

## Assumptions to validate

1. Parallel specialists improve completion time without reducing coherence.
2. Users value visible ownership and QA more than a long single-model answer.
3. Structured artifact contracts reduce integration failures.
4. Human approval is required before consequential external actions.

## Evaluation plan

| Dimension | MVP measure | Acceptance signal |
|---|---|---|
| Completeness | Required artifacts delivered | 100% contracts present |
| Quality | Reviewer rubric score | At least 0.78 |
| Coherence | Cross-artifact contradiction count | Zero critical conflicts |
| Efficiency | Wall time vs sequential baseline | Meaningful reduction |
| Control | Decisions with trace/owner | 100% |

## Risks and controls

- **Error propagation:** reviewers inspect each branch before integration.
- **Context overload:** workers receive bounded packets, not the entire transcript.
- **Runaway cost:** fixed graph, concurrency cap, and one revision maximum.
- **False confidence:** demo output labels assumptions and does not invent external evidence.
- **Unsafe actions:** generated code is never executed automatically.

## Recommendation

Build and test one vertical workflow, instrument every handoff, and add external tools only after the task graph is reliable. Real factual claims should be grounded with approved sources before release.
"""


def _code(objective: str) -> str:
    return f'''# Engineering Blueprint

## Target outcome

{_short(objective)}.

## Proposed modules

```text
api/            mission submission and status endpoints
orchestrator/   dependency scheduling, retries, termination
agents/         role prompts and artifact contracts
providers/      model-neutral adapters
storage/        run state, audit events, artifacts
ui/             control room and approval gates
tests/          graph, provider, failure, and API tests
```

## Core contract

```python
from dataclasses import dataclass

@dataclass
class WorkOrder:
    task_id: str
    objective: str
    inputs: dict[str, str]
    output_kind: str
    quality_threshold: float

@dataclass
class WorkResult:
    task_id: str
    content: str
    evidence: list[str]
    confidence: float
    status: str
```

## Scheduler pseudocode

```python
while unfinished_tasks:
    ready = [t for t in tasks if dependencies_complete(t)]
    results = execute_in_parallel(ready, max_workers=4)
    for result in results:
        review = reviewer.evaluate(result)
        if review.score < threshold and result.revision == 0:
            revise_once(result, review.feedback)
        persist(result, review)
```

## API surface

- `POST /api/runs` validates and starts a bounded mission.
- `GET /api/runs/{{id}}` returns graph, events, usage, and artifacts.
- `GET /api/runs/{{id}}/bundle` returns the integrated delivery.
- Provider keys remain server-side environment variables.

## Acceptance tests

1. Invalid objectives fail before an agent call.
2. Independent tasks overlap in execution.
3. Dependent tasks never start early.
4. Low-scoring work receives no more than one revision.
5. A provider failure marks the task and terminates cleanly.
6. Completed state can be loaded after restart.
'''


def _ux(objective: str) -> str:
    return f"""# Experience Specification

## Experience promise

For **{_short(objective)}**, the interface should feel like briefing a capable organization—not configuring a technical pipeline.

## Primary journey

1. **Brief:** write one outcome and optionally add context.
2. **Compose:** select the artifacts the organization must deliver.
3. **Deploy:** inspect the CEO's team and task dependencies.
4. **Observe:** watch ownership, activity, progress, and QA in real time.
5. **Decide:** review exceptions or approval gates.
6. **Collect:** preview and download the integrated package.

## Control-room layout

- **Left / Mission brief:** objective, templates, provider, deliverables, controls.
- **Centre / Organization:** CEO, departments, dependency-aware employee cards.
- **Right / Live ledger:** time-ordered actions and quality decisions.
- **Bottom / Delivery vault:** artifact previews, scores, and downloads.

## Required states

| State | User signal | Primary action |
|---|---|---|
| Empty | Suggested mission templates | Choose or type objective |
| Planning | CEO pulse and plan message | Wait / inspect scope |
| Running | Active employee + progress | Monitor |
| Reviewing | QA badge and score placeholder | Inspect criteria |
| Revising | Amber feedback state | See requested correction |
| Complete | Quality summary + artifacts | Preview/download |
| Failed | Plain-language cause | Retry safely |

## Accessibility and trust

- Never encode status with colour alone.
- Maintain readable contrast and keyboard-visible focus.
- Show which provider/model performed each role.
- Separate generated assumptions from verified evidence.
- Require confirmation before any external write or deployment.
"""


def _notes(objective: str) -> str:
    return f"""# Learning Notes

## What this mission is teaching

{_short(objective)}.

## Five concepts to remember

1. **Agent:** a model operating under a role, tools, context, and output contract.
2. **Orchestrator:** deterministic software that owns state, order, retries, and stopping.
3. **Task graph:** work expressed as nodes plus dependencies; it reveals what can run in parallel.
4. **Artifact contract:** an expected output type and quality rubric, not an open-ended chat reply.
5. **Human-in-the-loop:** an explicit approval point before high-impact actions.

## Why multiple agents can help

Specialization can improve focus, parallel branches can reduce wall time, and independent review can catch defects. More agents do **not** automatically mean better work: every handoff adds cost, latency, and another place for context to degrade.

## Practical design rule

Use deterministic code for control flow and models for judgement or generation. Start with the smallest graph that genuinely benefits from separate roles.

## Self-check

- Which tasks are truly independent?
- What exact artifact must each employee return?
- How will a reviewer measure quality?
- What happens after failure or disagreement?
- Which actions require a human decision?

## One-line summary

An AI organization is reliable when its delegation is bounded, its handoffs are structured, and every important result is observable and reviewable.
"""


def _slides(objective: str) -> str:
    return f"""# Presentation Outline

## Deck title

**From one objective to an accountable AI workforce**

**Mission:** {_short(objective)}.

### Slide 1 — The fragmented-work problem
- One outcome currently requires many disconnected AI tools.
- Context, ownership, and quality disappear between handoffs.
- Visual: scattered tools around one overwhelmed user.

### Slide 2 — Product thesis
- Brief an organization once; receive coordinated deliverables.
- The experience mirrors a company: CEO, managers, specialists, auditors.
- Visual: single input flowing into an organization chart.

### Slide 3 — How work moves
- CEO decomposes; router assigns; specialists execute in parallel.
- QA scores and requests one bounded revision.
- Integrator assembles the delivery bundle.

### Slide 4 — Why this is not just a group chat
- Explicit dependencies, persistent state, artifact contracts.
- Controlled retries, termination, budget, and traceability.
- Visual: task DAG beside an unstructured chat loop.

### Slide 5 — MVP experience
- Mission brief, organization view, live ledger, delivery vault.
- No key required for demo; real providers are pluggable.
- Visual: four annotated interface zones.

### Slide 6 — Trust architecture
- No automatic code execution.
- Server-side secrets and approval gates for external writes.
- Assumptions distinguished from verified evidence.

### Slide 7 — Success metrics
- Completion, reviewer quality, contradiction rate, wall time, cost.
- Compare against a sequential single-agent baseline.

### Slide 8 — Differentiation
- Capability-aware routing and multi-format assembly.
- Observable corporate metaphor understandable to non-technical users.
- Provider-neutral core reduces lock-in.

### Slide 9 — Expansion path
- MCP tool registry, Notion/GitHub/presentation adapters.
- Human approvals, team memory, learning-based routing.
- Start narrow; expand only after evaluation.

### Slide 10 — Ask / next step
- Run the first design-partner mission.
- Measure quality and time against the existing workflow.
- Decide the first external integration from observed demand.
"""
