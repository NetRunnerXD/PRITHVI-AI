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
    """Resolve npm without the broken Windows nested npm\\bin shim.

    Some Node installs put ``...\\nodejs\\node_modules\\npm\\bin`` ahead of
    ``...\\nodejs`` on PATH. That shim looks for
    ``npm\\bin\\node_modules\\npm\\bin\\npm-cli.js`` and crashes.
    """
    names = ("npm.cmd", "npm.exe", "npm") if os.name == "nt" else ("npm",)
    nested = os.path.normcase(os.path.join("node_modules", "npm", "bin"))
    node_dir = os.path.dirname(shutil.which("node") or "")
    if node_dir:
        for name in names:
            candidate = os.path.join(node_dir, name)
            if os.path.isfile(candidate):
                return candidate
        cli = os.path.join(node_dir, "node_modules", "npm", "bin", "npm-cli.js")
        if os.path.isfile(cli):
            return cli
    for name in names:
        found = shutil.which(name)
        if found and nested not in os.path.normcase(found):
            return found
    if os.name == "nt":
        for extra in (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "nodejs",
        ):
            for name in ("npm.cmd", "npm.exe"):
                candidate = extra / name
                if candidate.is_file():
                    return str(candidate)
    return None


def _web_env(npm: str) -> dict[str, str]:
    """Ensure node.exe is on PATH for npm.cmd and frontend/node_modules/.bin shims."""
    env = os.environ.copy()
    node_dirs: list[str] = []
    npm_dir = str(Path(npm).resolve().parent)
    if (Path(npm_dir) / "node.exe").is_file() or (Path(npm_dir) / "node").is_file():
        node_dirs.append(npm_dir)
    node_bin = shutil.which("node") or shutil.which("node.exe")
    if node_bin:
        node_dirs.append(str(Path(node_bin).resolve().parent))
    if not node_dirs:
        return env
    path_key = "Path" if "Path" in env and "PATH" not in env else "PATH"
    current = env.get(path_key, "")
    prefix = os.pathsep.join(dict.fromkeys(node_dirs))
    env[path_key] = prefix + os.pathsep + current if current else prefix
    return env


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
                if npm.lower().endswith(".js"):
                    node = shutil.which("node") or "node"
                    npm_cmd = [node, npm, "run", "dev"]
                else:
                    npm_cmd = [npm, "run", "dev"]
                web = subprocess.Popen(npm_cmd, cwd=FRONTEND, env=_web_env(npm))
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
