"""Start Rituchakra: FastAPI API on :8000 and the Next.js dashboard on :3000."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def _stop(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()


def _port_busy(host: str, port: int) -> bool:
    import socket

    bind = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        try:
            return s.connect_ex((bind, port)) == 0
        except OSError:
            return False


def _npm() -> str | None:
    names = ("npm.cmd", "npm.exe", "npm") if os.name == "nt" else ("npm",)
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the Rituchakra web app")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--api-only", action="store_true", help="Start only the FastAPI API")
    parser.add_argument("--reload", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    if not (BACKEND / "app" / "main.py").is_file():
        print("backend/app/main.py not found", file=sys.stderr)
        return 1

    api_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if args.reload:
        api_cmd.append("--reload")

    origin = f"http://{args.host}:{args.port}"
    if _port_busy(args.host, args.port):
        print(
            f"Port {args.port} is already in use. Stop the other uvicorn / python main.py "
            f"or start with --port 8001.\n"
            f"Health of whatever is bound: {origin}/api/health",
            file=sys.stderr,
        )
        return 1
    print(f"API        {origin}/docs")
    print(f"Health     {origin}/api/health")

    children: list[subprocess.Popen[bytes]] = []
    web: subprocess.Popen[bytes] | None = None
    try:
        api = subprocess.Popen(api_cmd, cwd=BACKEND)
        children.append(api)
        time.sleep(0.8)
        if api.poll() is not None:
            print(
                f"API exited immediately ({api.returncode}). "
                f"Run from backend/:  python -m uvicorn app.main:app --host {args.host} --port {args.port}",
                file=sys.stderr,
            )
            return api.returncode or 1

        if not args.api_only:
            npm = _npm()
            if not (FRONTEND / "package.json").is_file():
                print("Frontend skipped: frontend/package.json missing")
            elif npm is None:
                print("Frontend skipped: npm not on PATH")
            elif not (FRONTEND / "node_modules").is_dir():
                print("Frontend skipped: run  cd frontend ; npm install")
            else:
                web = subprocess.Popen([npm, "run", "dev"], cwd=FRONTEND)
                children.append(web)
                print("Dashboard  http://localhost:3000")

        print("Ctrl+C to stop")
        while True:
            if api.poll() is not None:
                return api.returncode or 0
            if web is not None and web.poll() is not None:
                code = web.returncode or 0
                print(f"Frontend exited ({code})", file=sys.stderr)
                web = None
            time.sleep(0.4)
    except KeyboardInterrupt:
        print("\nStopping")
        return 0
    finally:
        for proc in reversed(children):
            _stop(proc)


if __name__ == "__main__":
    raise SystemExit(main())
