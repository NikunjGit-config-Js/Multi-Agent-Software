# OrgMind

**One objective in. A coordinated AI workforce out.**

OrgMind is a runnable MVP of a corporate-style multi-agent system. A CEO agent
turns a goal into a task graph, specialist departments work in parallel,
reviewers score and revise the work, and an integration agent packages the
result into one delivery bundle.

The project deliberately works in two modes:

- **Demo mode** runs locally with no API key and is useful for understanding,
  presenting, and testing the orchestration system.
- **Live model mode** connects the same workflow to an OpenAI-compatible API or
  Anthropic. Provider credentials stay in environment variables.

## What is implemented

- CEO planning and capability-aware routing
- Department managers that issue bounded work orders to leaf specialists
- Research, engineering, UX, notes, and presentation departments
- Explicit dependency graph instead of an unbounded agent chat
- Parallel execution of independent departments
- Independent QA, one controlled revision attempt, and final integration
- Live run timeline, hierarchy view, quality scores, cost/latency telemetry
- Downloadable Markdown, code, presentation-outline, and manifest artifacts
- Persistent local run history under `data/runs/`
- Provider-neutral model adapter with per-role model routing
- No generated code execution and no secret storage in the browser

## Quick start

Python 3.10+ is the only runtime requirement.

```bash
cd orgmind
python app.py
```

Open <http://127.0.0.1:8080>, keep **Demo workforce** selected, choose the
deliverables, and launch a mission.

To use another port:

```bash
python app.py --port 9000
```

## Connect a real model

Copy `.env.example` to `.env`, add a key, then load the variables in your shell.
OrgMind never writes API keys to run files or sends them to the browser.

### OpenAI-compatible

```bash
export ORGMIND_PROVIDER=openai
export OPENAI_API_KEY="..."
export ORGMIND_CEO_MODEL="gpt-4.1-mini"
export ORGMIND_WORKER_MODEL="gpt-4.1-mini"
export ORGMIND_REVIEWER_MODEL="gpt-4.1-mini"
python app.py
```

Set `OPENAI_BASE_URL` when using another OpenAI-compatible service.

### Anthropic

```bash
export ORGMIND_PROVIDER=anthropic
export ANTHROPIC_API_KEY="..."
export ORGMIND_CEO_MODEL="claude-sonnet-4-20250514"
export ORGMIND_WORKER_MODEL="claude-sonnet-4-20250514"
export ORGMIND_REVIEWER_MODEL="claude-sonnet-4-20250514"
python app.py
```

Model names above are examples; choose models available in your own account.

## Architecture

```text
User objective
    -> CEO planner
       -> Department managers
          -> Research specialist ----\
          -> Engineering specialist --+-> QA & controlled revision
          -> UX specialist -----------/              |
          -> Notes specialist (may depend on research)
          -> Presentation specialist (depends on prior outputs)
                                                   -> Integration executive
                                                      -> delivery bundle
```

Every manager receives the CEO brief and issues a bounded work order. A leaf
specialist then receives only the relevant context packet and returns an
artifact with an explicit contract. The orchestrator, not an LLM conversation,
owns state, dependencies, retries, concurrency, and termination.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Runtime health and provider readiness |
| `GET` | `/api/templates` | Starter mission templates |
| `GET` | `/api/runs` | Recent runs |
| `POST` | `/api/runs` | Start a mission |
| `GET` | `/api/runs/{id}` | Poll complete run state |
| `GET` | `/api/runs/{id}/artifacts/{artifact_id}` | Download an artifact |
| `GET` | `/api/runs/{id}/bundle` | Download the final Markdown bundle |

Example:

```bash
curl -X POST http://127.0.0.1:8080/api/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "objective": "Design a fraud-risk dashboard for a bank",
    "deliverables": ["research", "code", "ux", "notes", "slides"],
    "provider": "demo",
    "quality_threshold": 0.78
  }'
```

## Tests

```bash
python -m unittest discover -s tests -v
```

## Boundaries of this MVP

Notion, Gamma, NotebookLM, GitHub, and deployment services require their own
permissions and APIs. OrgMind models them as capability slots today; adapters
can be added without changing the orchestration engine. The next production
step is an MCP/tool registry plus human approval gates for external writes.

## Portfolio positioning

Do not present OrgMind as “the first multi-agent system.” Present the concrete
engineering contribution:

> A provider-neutral, capability-aware AI organization that compiles one user
> objective into a bounded dependency graph, executes specialist work in
> parallel, validates each artifact, and assembles a traceable multi-format
> delivery bundle.
