"""Stop old copies, then start the Prithvi AI processes.

FastAPI on :8000, the Next.js dashboard on :3000, IndicTrans2 on :8093,
FastSpeech2 on :7860, and Indic STT on :8091 when that server is installed.
VEXYL TTS is not a speaker and is not started.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
# server.py binds this port itself. LOCAL_TTS_DIR overrides the checkout.
TTS_PORT = 7860
TTS_ROOT = Path(os.environ.get("LOCAL_TTS_DIR", r"D:\Project\Random\ai tts"))


def _stop(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    if os.name == "nt":
        # The translation sidecar re-execs into backend/.venv. Killing the
        # parent alone leaves that child listening.
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
        )
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
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


def _env_file_value(key: str) -> str:
    path = BACKEND / ".env"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        name, val = raw.split("=", 1)
        if name.strip() == key:
            return val.strip().strip('"').strip("'")
    return ""


def _port_from_url(url: str, default: int) -> int:
    raw = (url or "").strip()
    if not raw:
        return default
    if "://" not in raw:
        raw = "http://" + raw
    try:
        port = urlparse(raw).port
    except ValueError:
        return default
    return port or default


def _mt_port() -> int:
    raw = (os.environ.get("MT_SIDECAR_PORT") or "").strip()
    if raw.isdigit():
        return int(raw)
    url = (os.environ.get("MT_SIDECAR_URL") or _env_file_value("MT_SIDECAR_URL")).strip()
    return _port_from_url(url, 8093)


def _stt_port() -> int:
    url = (os.environ.get("VEXYL_STT_URL") or _env_file_value("VEXYL_STT_URL")).strip()
    if url:
        return _port_from_url(url, 8091)
    raw = (os.environ.get("VEXYL_STT_PORT") or "").strip()
    if raw.isdigit():
        return int(raw)
    return 8091


def _stt_root() -> Path | None:
    override = (os.environ.get("VEXYL_STT_DIR") or "").strip()
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override))
    candidates.extend(
        [
            Path(r"D:\Project\Random\RainFall\voice\vexyl-stt"),
            Path(r"D:\Project\Random\Research\PRITHVI-AI\voice\vexyl-stt"),
        ]
    )
    for path in candidates:
        if (path / "vexyl_stt_server.py").is_file():
            return path
    return None


def _tts_python() -> Path | None:
    folder = "Scripts" if os.name == "nt" else "bin"
    name = "python.exe" if os.name == "nt" else "python"
    candidate = TTS_ROOT / ".venv" / folder / name
    return candidate if candidate.is_file() else None


def _stt_python() -> Path:
    """Transformers 4.x lives in backend/.venv. IndicConformer stays out of the API process."""
    folder = "Scripts" if os.name == "nt" else "bin"
    name = "python.exe" if os.name == "nt" else "python"
    candidate = BACKEND / ".venv" / folder / name
    return candidate if candidate.is_file() else Path(sys.executable)


def _kill_running_servers(
    backend_port: int = 8000,
    frontend_port: int = 3000,
    *,
    sidecars: bool = True,
) -> None:
    """Stop API, dashboard, and (unless --api-only) translation and speech."""
    mt_port = _mt_port()
    stt_port = _stt_port()
    stt_root = _stt_root() if sidecars else None
    names = [f"API :{backend_port}", f"dashboard :{frontend_port}"]
    ports = [backend_port, frontend_port]
    if sidecars:
        names.extend([f"translation :{mt_port}", f"speaker :{TTS_PORT}"])
        ports.extend([mt_port, TTS_PORT])
        if stt_root is not None:
            names.append(f"Indic STT :{stt_port}")
            ports.append(stt_port)
    print("Stopping " + ", ".join(names) + "...", flush=True)
    for port in ports:
        _kill_port(port)

    if os.name == "nt":
        try:
            extra = ""
            if sidecars:
                extra = (
                    " -or ($_.Name -like '*python*' -and $_.CommandLine -like '*mt_sidecar.py*')"
                    " -or ($_.Name -like '*python*' -and $_.CommandLine -like '*server.py*' -and "
                    "($_.ExecutablePath -like '*\\ai tts\\*' -or $_.CommandLine -like '*ai tts*'))"
                )
                if stt_root is not None:
                    extra += " -or ($_.Name -like '*python*' -and $_.CommandLine -like '*vexyl_stt_server.py*')"
            ps_script = (
                f"$cur = {os.getpid()}; "
                "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { "
                "($_.ProcessId -ne $cur) -and ("
                "($_.Name -like '*python*' -and ($_.CommandLine -like '*uvicorn*' -or $_.CommandLine -like '*app.main:app*' -or $_.CommandLine -like '*spawn_main*')) -or "
                "($_.Name -like '*node*' -and ($_.CommandLine -like '*next*' -or $_.CommandLine -like '*npm*'))"
                + extra
                + ") } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True)
        except Exception:
            pass
    else:
        try:
            subprocess.run("pkill -9 -f 'uvicorn.*app.main:app' 2>/dev/null || true", shell=True)
            subprocess.run("pkill -9 -f 'next-server' 2>/dev/null || true", shell=True)
            if sidecars:
                subprocess.run("pkill -9 -f 'mt_sidecar.py' 2>/dev/null || true", shell=True)
                tts_pat = str(TTS_ROOT).replace("'", "")
                subprocess.run(f"pkill -9 -f '{tts_pat}' 2>/dev/null || true", shell=True)
                if stt_root is not None:
                    subprocess.run("pkill -9 -f 'vexyl_stt_server.py' 2>/dev/null || true", shell=True)
        except Exception:
            pass

    spins = 75 if sidecars else 25
    for _ in range(spins):
        if all(not _port_busy("127.0.0.1", port) for port in ports):
            break
        time.sleep(0.2)
    print("Cleanup complete.", flush=True)


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


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _note_early_exit(label: str, proc: subprocess.Popen[bytes] | None) -> None:
    if proc is not None and proc.poll() is not None:
        print(f"{label} exited immediately ({proc.returncode})", file=sys.stderr)


def _start_translation(port: int) -> subprocess.Popen[bytes] | None:
    script = BACKEND / "scripts" / "mt_sidecar.py"
    venv = BACKEND / ".venv"
    if not script.is_file():
        print("Translation skipped: backend/scripts/mt_sidecar.py missing")
        return None
    if not venv.is_dir():
        print("Translation skipped: backend/.venv missing (IndicTrans2 needs transformers 4.x)")
        return None
    if _port_busy("127.0.0.1", port):
        print(f"Translation left running: port {port} is still in use")
        return None
    print(f"Translation http://127.0.0.1:{port}")
    # The script relaunches itself with backend/.venv when the default Python is 5.x.
    return subprocess.Popen([sys.executable, str(script)], cwd=BACKEND, env=_child_env())


def _start_speaker() -> subprocess.Popen[bytes] | None:
    script = TTS_ROOT / "server.py"
    py = _tts_python()
    if not script.is_file():
        print(f"Speaker skipped: {script} missing")
        return None
    if py is None:
        print(f"Speaker skipped: {TTS_ROOT / '.venv'} missing")
        return None
    if _port_busy("127.0.0.1", TTS_PORT):
        print(f"Speaker left running: port {TTS_PORT} is still in use")
        return None
    print(f"Speaker    http://127.0.0.1:{TTS_PORT}")
    return subprocess.Popen([str(py), str(script)], cwd=TTS_ROOT, env=_child_env())


def _start_stt(port: int) -> subprocess.Popen[bytes] | None:
    root = _stt_root()
    if root is None:
        print("Indic STT skipped: vexyl_stt_server.py was not found")
        return None
    if _port_busy("127.0.0.1", port):
        print(f"Indic STT left running: port {port} is still in use")
        return None
    env = _child_env()
    # This server reads PORT before VEXYL_STT_PORT. The shell PORT is the API port.
    env["VEXYL_STT_HOST"] = "127.0.0.1"
    env["VEXYL_STT_PORT"] = str(port)
    env["PORT"] = str(port)
    if not (env.get("HF_TOKEN") or env.get("HUGGING_FACE_HUB_TOKEN") or "").strip():
        token = _env_file_value("HF_TOKEN") or _env_file_value("HUGGING_FACE_HUB_TOKEN")
        if token:
            env["HF_TOKEN"] = token
            env["HUGGING_FACE_HUB_TOKEN"] = token
    key = (env.get("VEXYL_API_KEY") or _env_file_value("VEXYL_API_KEY")).strip()
    if key and not (env.get("VEXYL_STT_API_KEY") or "").strip():
        env["VEXYL_STT_API_KEY"] = key
    print(f"Indic STT  http://127.0.0.1:{port}")
    return subprocess.Popen(
        [str(_stt_python()), str(root / "vexyl_stt_server.py")],
        cwd=root,
        env=env,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Stop old copies, then start Prithvi AI")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--frontend-port", type=int, default=3000, help="Frontend port (default 3000)")
    parser.add_argument("--no-kill", action="store_true", help="Do not kill existing servers before starting")
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Start only the FastAPI API. Do not stop or start translation and speech",
    )
    parser.add_argument("--reload", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    start_sidecars = not args.api_only
    if not args.no_kill:
        _kill_running_servers(
            backend_port=args.port,
            frontend_port=args.frontend_port,
            sidecars=start_sidecars,
        )

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
        # Watch application code only. GFS writes backend/.cache/gfs/*.npz at startup;
        # watching the whole backend reloads Uvicorn mid-download and the new process never binds.
        api_cmd.extend(["--reload", "--reload-dir", "app"])

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
    translation: subprocess.Popen[bytes] | None = None
    speaker: subprocess.Popen[bytes] | None = None
    stt: subprocess.Popen[bytes] | None = None
    try:
        if start_sidecars:
            translation = _start_translation(_mt_port())
            speaker = _start_speaker()
            stt = _start_stt(_stt_port())
            for proc in (translation, speaker, stt):
                if proc is not None:
                    children.append(proc)

        api = subprocess.Popen(api_cmd, cwd=BACKEND)
        children.append(api)
        time.sleep(0.8)
        _note_early_exit("Translation", translation)
        _note_early_exit("Speaker", speaker)
        _note_early_exit("Indic STT", stt)
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
        watch: list[tuple[str, subprocess.Popen[bytes]]] = []
        if web is not None:
            watch.append(("Frontend", web))
        if translation is not None:
            watch.append(("Translation", translation))
        if speaker is not None:
            watch.append(("Speaker", speaker))
        if stt is not None:
            watch.append(("Indic STT", stt))
        noted: set[int] = set()
        while True:
            if api.poll() is not None:
                return api.returncode or 0
            for label, proc in watch:
                if proc.poll() is None or proc.pid in noted:
                    continue
                noted.add(proc.pid)
                print(f"{label} exited ({proc.returncode or 0})", file=sys.stderr)
            time.sleep(0.4)
    except KeyboardInterrupt:
        print("\nStopping")
        return 0
    finally:
        for proc in reversed(children):
            _stop(proc)


if __name__ == "__main__":
    raise SystemExit(main())
