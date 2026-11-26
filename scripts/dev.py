"""Start isolated local demo without Docker/Redis. Run with project Python 3.12."""

import os, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
env = {
    **os.environ,
    "DEBUG": "true",
    "DATABASE_URL": f"sqlite:///{ROOT / 'backend' / 'db.sqlite3'}",
    "ALLOW_DEMO": "true",
    "DEMO_ORIGIN": "http://127.0.0.1:8090",
    "LOCAL_DEMO_RUNNER": "true",
    "LOCAL_CHANNELS": "true",
    "CELERY_TASK_ALWAYS_EAGER": "false",
    "PYTHONUNBUFFERED": "1",
}
processes = []


def start(args, cwd=ROOT):
    process = subprocess.Popen(args, cwd=cwd, env=env)
    processes.append(process)
    return process


def main():
    for command in ["migrate", "seed_templates"]:
        subprocess.run(
            [sys.executable, "manage.py", command],
            cwd=ROOT / "backend",
            env=env,
            check=True,
        )
    start([sys.executable, "demo-sites/server.py"])
    start(
        [
            sys.executable,
            "-m",
            "daphne",
            "-b",
            "127.0.0.1",
            "-p",
            "8000",
            "config.asgi:application",
        ],
        ROOT / "backend",
    )
    start([sys.executable, "manage.py", "run_demo"], ROOT / "backend")
    import urllib.request, urllib.error

    for _ in range(100):
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/api/v1/auth/me/", timeout=0.3)
            break
        except urllib.error.HTTPError:
            break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError("Backend startup timed out")
    start(
        ["cmd", "/c", "npm", "run", "dev"]
        if os.name == "nt"
        else ["npm", "run", "dev"],
        ROOT / "frontend",
    )
    print(
        "\nBrowserFlow local demo: http://localhost:5173\nRunner: local database polling; deployment: Celery + Redis.\nRegister a new account in the UI. Ctrl+C stops owned services.",
        flush=True,
    )
    try:
        while all(p.poll() is None for p in processes):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for p in reversed(processes):
            if p.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(p.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    p.terminate()
        for p in processes:
            try:
                p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
