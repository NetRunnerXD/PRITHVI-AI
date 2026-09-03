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

    targets = [host]
    if host in {"0.0.0.0", "::", "127.0.0.1"}:
        targets = ["127.0.0.1", "::1"]
    for target in targets:
        family = socket.AF_INET6 if ":" in target else socket.AF_INET
        try:
            with socket.socket(family, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex((target, port)) == 0:
                    return True
        except OSError:
            pass
    return False


def _kill_port(port: int) -> list[int]:
    """Kill any process listening on the specified port (IPv4 and IPv6)."""
    killed: list[int] = []
    current_pid = os.getpid()
    if os.name == "nt":
        pids: set[int] = set()
        # 1. Query via PowerShell Get-NetTCPConnection (catches both IPv4 and IPv6)
        try:
            ps_cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess",
            ]
            out = subprocess.check_output(ps_cmd, text=True, errors="ignore")
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit():
                    p = int(line)
                    if p > 0 and p != current_pid:
                        pids.add(p)
        except Exception:
            pass

        # 2. Fallback / supplement with netstat -ano
        try:
            out = subprocess.check_output("netstat -ano", shell=True, text=True, errors="ignore")
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 5 and "TCP" in parts[0].upper():
                    local_addr = parts[1]
                    state = parts[3].upper()
                    pid_str = parts[4]
                    if (local_addr.endswith(f":{port}") or local_addr.endswith(f"]:{port}")) and state in ("LISTENING", "CLOSE_WAIT"):
                        try:
                            p = int(pid_str)
                            if p > 0 and p != current_pid:
                                pids.add(p)
                        except ValueError:
                            pass
        except Exception:
            pass

        for pid in pids:
            res = subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, capture_output=True)
            if res.returncode == 0:
                killed.append(pid)
    else:
        try:
            out = subprocess.check_output(f"lsof -ti:{port} 2>/dev/null || true", shell=True, text=True)
            for line in out.splitlines():
                try:
                    p = int(line.strip())
                    if p > 0 and p != current_pid:
                        subprocess.run(f"kill -9 {p} 2>/dev/null", shell=True)
                        killed.append(p)
                except ValueError:
                    pass
        except Exception:
            pass
    return killed


def _kill_running_servers(backend_port: int = 8000, frontend_port: int = 3000) -> None:
    """Kill all running frontend (Next.js) and backend (FastAPI/uvicorn) instances."""
    print(f"Stopping any running backend (:{backend_port}) and frontend (:{frontend_port}) instances...", flush=True)
    _kill_port(backend_port)
    _kill_port(frontend_port)

    if os.name == "nt":
        try:
            ps_script = (
                f"$cur = {os.getpid()}; "
                "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { "
                "($_.ProcessId -ne $cur) -and ("
                "($_.Name -like '*python*' -and ($_.CommandLine -like '*uvicorn*' -or $_.CommandLine -like '*app.main:app*' -or $_.CommandLine -like '*spawn_main*')) -or "
                "($_.Name -like '*node*' -and ($_.CommandLine -like '*next*' -or $_.CommandLine -like '*npm*'))"
                ") } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True)
        except Exception:
            pass
    else:
        try:
            subprocess.run("pkill -9 -f 'uvicorn.*app.main:app' 2>/dev/null || true", shell=True)
            subprocess.run("pkill -9 -f 'next-server' 2>/dev/null || true", shell=True)
        except Exception:
            pass

    # Wait for ports to be completely released
    for _ in range(25):
        if not _port_busy("127.0.0.1", backend_port) and not _port_busy("127.0.0.1", frontend_port):
            break
        time.sleep(0.2)
    print("Cleanup complete. Starting fresh backend and frontend instances...", flush=True)


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
    parser.add_argument("--frontend-port", type=int, default=3000, help="Frontend port (default 3000)")
    parser.add_argument("--no-kill", action="store_true", help="Do not kill existing servers before starting")
    parser.add_argument("--api-only", action="store_true", help="Start only the FastAPI API")
    parser.add_argument("--reload", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    if not args.no_kill:
        _kill_running_servers(backend_port=args.port, frontend_port=args.frontend_port)

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
            f"Port {args.port} is already in use after cleanup attempt. "
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
                port_args = [] if args.frontend_port == 3000 else ["--", "-p", str(args.frontend_port)]
                if npm.lower().endswith(".js"):
                    node = shutil.which("node") or "node"
                    npm_cmd = [node, npm, "run", "dev", *port_args]
                else:
                    npm_cmd = [npm, "run", "dev", *port_args]
                web_env = _web_env(npm)
                web_env["PORT"] = str(args.frontend_port)
                web = subprocess.Popen(npm_cmd, cwd=FRONTEND, env=web_env)
                children.append(web)
                print(f"Dashboard  http://localhost:{args.frontend_port}")

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
