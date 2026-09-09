"""Cross-platform developer commands. Run from any working directory."""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
PYTHON = BACKEND / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
NPM = shutil.which("npm.cmd" if os.name == "nt" else "npm") or "npm"


def run(args: list[str], cwd: Path = ROOT) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def backend(*args: str) -> None:
    run([str(PYTHON), "-m", *args], BACKEND)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "setup",
            "dev",
            "test",
            "lint",
            "build",
            "migrate",
            "db-up",
            "db-down",
        ],
    )
    command = parser.parse_args().command
    if command == "setup":
        for source, destination in [
            (ROOT / ".env.example", ROOT / ".env"),
            (FRONTEND / ".env.example", FRONTEND / ".env.local"),
        ]:
            if not destination.exists():
                shutil.copyfile(source, destination)
        if not PYTHON.exists():
            run([sys.executable, "-m", "venv", str(BACKEND / ".venv")])
        backend("pip", "install", "-r", "requirements-dev.lock", "-e", ".[dev]")
        run([NPM, "ci"], FRONTEND)
    elif command == "db-up":
        run(["docker", "compose", "up", "-d", "--wait"])
    elif command == "db-down":
        run(["docker", "compose", "down"])
    elif command == "migrate":
        backend("alembic", "upgrade", "head")
    elif command == "test":
        backend("pytest")
        run([NPM, "test"], FRONTEND)
    elif command == "lint":
        backend("ruff", "check", ".", "../scripts")
        backend("ruff", "format", "--check", ".", "../scripts")
        backend("mypy", "app")
        run([NPM, "run", "lint"], FRONTEND)
        run([NPM, "run", "format:check"], FRONTEND)
        run([NPM, "run", "typecheck"], FRONTEND)
    elif command == "build":
        run([NPM, "run", "build"], FRONTEND)
    elif command == "dev":
        run(["docker", "compose", "up", "-d", "--wait"])
        backend("alembic", "upgrade", "head")
        processes: list[subprocess.Popen[bytes]] = []
        try:
            processes.append(
                subprocess.Popen(
                    [str(PYTHON), "-m", "uvicorn", "app.main:app", "--reload"],
                    cwd=BACKEND,
                )
            )
            processes.append(subprocess.Popen([NPM, "run", "dev"], cwd=FRONTEND))
            while all(process.poll() is None for process in processes):
                time.sleep(0.5)
            raise RuntimeError("A development server exited; stopping both servers.")
        except KeyboardInterrupt:
            pass
        finally:
            for process in processes:
                if process.poll() is None:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            check=False,
                            stdout=subprocess.DEVNULL,
                        )
                    else:
                        process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, FileNotFoundError, RuntimeError) as error:
        print(f"Command failed: {error}", file=sys.stderr)
        sys.exit(1)
