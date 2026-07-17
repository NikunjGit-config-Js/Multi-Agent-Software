from __future__ import annotations

import json
import mimetypes
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .models import MissionRequest
from .orchestrator import Orchestrator
from .providers import provider_readiness
from .storage import RunStore
from .templates import TEMPLATES


class OrgMindApp:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        data_dir = Path(os.getenv("ORGMIND_DATA_DIR", "data/runs"))
        if not data_dir.is_absolute():
            data_dir = self.project_root / data_dir
        self.store = RunStore(data_dir)
        self.orchestrator = Orchestrator(self.store)
        self.static_dir = self.project_root / "static"

    def handler_class(self) -> type[BaseHTTPRequestHandler]:
        app = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "OrgMind/0.1"

            def do_GET(self) -> None:  # noqa: N802
                app.handle_get(self)

            def do_POST(self) -> None:  # noqa: N802
                app.handle_post(self)

            def log_message(self, fmt: str, *args: object) -> None:
                if os.getenv("ORGMIND_QUIET", "").lower() not in {"1", "true"}:
                    super().log_message(fmt, *args)

        return Handler

    def handle_get(self, handler: BaseHTTPRequestHandler) -> None:
        path = unquote(urlparse(handler.path).path)
        if path == "/api/health":
            self._json(
                handler,
                {
                    "ok": True,
                    "service": "OrgMind",
                    "version": "0.1.0",
                    "providers": provider_readiness(),
                },
            )
            return
        if path == "/api/templates":
            self._json(handler, {"templates": TEMPLATES})
            return
        if path == "/api/runs":
            self._json(handler, {"runs": self.store.recent()})
            return
        match = re.fullmatch(r"/api/runs/([a-zA-Z0-9_-]+)", path)
        if match:
            snapshot = self.store.snapshot(match.group(1), include_content=False)
            if snapshot is None:
                self._error(handler, HTTPStatus.NOT_FOUND, "Run not found")
            else:
                self._json(handler, snapshot)
            return
        match = re.fullmatch(
            r"/api/runs/([a-zA-Z0-9_-]+)/artifacts/([a-zA-Z0-9_-]+)", path
        )
        if match:
            self._artifact(handler, match.group(1), match.group(2))
            return
        match = re.fullmatch(r"/api/runs/([a-zA-Z0-9_-]+)/bundle", path)
        if match:
            run = self.store.get(match.group(1))
            if not run or not run.bundle_artifact_id:
                self._error(handler, HTTPStatus.NOT_FOUND, "Delivery bundle is not ready")
            else:
                self._artifact(handler, run.id, run.bundle_artifact_id)
            return
        self._static(handler, path)

    def handle_post(self, handler: BaseHTTPRequestHandler) -> None:
        path = urlparse(handler.path).path
        if path != "/api/runs":
            self._error(handler, HTTPStatus.NOT_FOUND, "Endpoint not found")
            return
        try:
            length = int(handler.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise ValueError("Request body must be between 1 byte and 1 MB")
            payload = json.loads(handler.rfile.read(length).decode("utf-8"))
            provider = str(payload.get("provider") or os.getenv("ORGMIND_PROVIDER", "demo"))
            readiness = provider_readiness()
            if provider not in readiness or not readiness[provider]["ready"]:
                raise ValueError(f"Provider '{provider}' is not configured on the server")
            request = MissionRequest(
                objective=str(payload.get("objective", "")),
                deliverables=list(payload.get("deliverables") or []),
                provider=provider,
                quality_threshold=float(payload.get("quality_threshold", 0.78)),
                max_parallel=int(
                    payload.get("max_parallel", os.getenv("ORGMIND_MAX_PARALLEL", "4"))
                ),
                context=str(payload.get("context", "")),
            )
            run = self.orchestrator.start(request)
            self._json(handler, {"run_id": run.id, "status": run.status}, HTTPStatus.ACCEPTED)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._error(handler, HTTPStatus.BAD_REQUEST, str(exc))

    def _artifact(self, handler: BaseHTTPRequestHandler, run_id: str, artifact_id: str) -> None:
        run = self.store.get(run_id)
        artifact = next((item for item in run.artifacts if item.id == artifact_id), None) if run else None
        if artifact is None:
            self._error(handler, HTTPStatus.NOT_FOUND, "Artifact not found")
            return
        body = artifact.content.encode("utf-8")
        content_type = "application/json" if artifact.filename.endswith(".json") else "text/markdown"
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", f"{content_type}; charset=utf-8")
        handler.send_header("Content-Disposition", f'attachment; filename="{artifact.filename}"')
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        handler.wfile.write(body)

    def _static(self, handler: BaseHTTPRequestHandler, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        target = (self.static_dir / relative).resolve()
        if self.static_dir not in target.parents and target != self.static_dir:
            self._error(handler, HTTPStatus.NOT_FOUND, "File not found")
            return
        if not target.is_file():
            target = self.static_dir / "index.html"
        try:
            body = target.read_bytes()
        except OSError:
            self._error(handler, HTTPStatus.NOT_FOUND, "File not found")
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", f"{content_type}; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-cache")
        handler.end_headers()
        handler.wfile.write(body)

    @staticmethod
    def _json(
        handler: BaseHTTPRequestHandler,
        payload: object,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        handler.wfile.write(body)

    @classmethod
    def _error(cls, handler: BaseHTTPRequestHandler, status: HTTPStatus, message: str) -> None:
        cls._json(handler, {"error": message}, status)


def serve(project_root: str | Path, host: str, port: int) -> None:
    app = OrgMindApp(project_root)
    server = ThreadingHTTPServer((host, port), app.handler_class())
    print(f"OrgMind is ready at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

