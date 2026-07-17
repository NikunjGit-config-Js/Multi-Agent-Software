from __future__ import annotations

import argparse
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def main() -> None:
    load_env(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Run the OrgMind AI workforce control room")
    parser.add_argument("--host", default=os.getenv("ORGMIND_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("ORGMIND_PORT", "8080")))
    args = parser.parse_args()

    from orgmind.server import serve

    serve(ROOT, args.host, args.port)


if __name__ == "__main__":
    main()

