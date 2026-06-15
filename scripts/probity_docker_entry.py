"""Small Docker entrypoint for common Probity local commands."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO_TASK = "demo/patchbot/task_demo_patchbot_01.json"


HELP = """Probity Docker commands:

  demo-once          Run the single-run demo that looks shippable.
  demo               Run the repeated demo. KILL is expected and exits 0 here.
  calibrate          Run the 10-case calibration gate.
  test               Run the Python test suite.
  run <task.json>    Run Probity on a task file. Preserves real verdict exit code.
  report <audit>     Re-render an audit JSON report.
  shell              Open /bin/sh.

Examples:
  docker run --rm probity demo
  docker run --rm probity calibrate
  docker run --rm -v "$PWD:/work" probity run /work/task_case.json
"""


def _run(args: list[str]) -> int:
    proc = subprocess.run(args, cwd=ROOT, text=True)
    return proc.returncode


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "help"
    rest = argv[2:]

    if cmd in {"help", "-h", "--help"}:
        print(HELP)
        return 0
    if cmd == "demo-once":
        return _run([sys.executable, "-m", "gauntlet", "run", DEMO_TASK, "--once", "--seed", "1"])
    if cmd == "demo":
        code = _run([sys.executable, "-m", "gauntlet", "run", DEMO_TASK])
        if code == 1:
            print("\nDocker demo note: KILL is the expected demo verdict, so this wrapper exits 0.")
            return 0
        return code
    if cmd == "calibrate":
        return _run([sys.executable, "-m", "gauntlet", "calibrate"])
    if cmd == "test":
        return _run([sys.executable, "-m", "pytest", "-q"])
    if cmd == "run":
        if not rest:
            print("usage: docker run --rm probity run <task_case.json> [gauntlet args...]", file=sys.stderr)
            return 2
        return _run([sys.executable, "-m", "gauntlet", "run", *rest])
    if cmd == "report":
        if not rest:
            print("usage: docker run --rm probity report <audit_report.json>", file=sys.stderr)
            return 2
        return _run([sys.executable, "-m", "gauntlet", "report", *rest])
    if cmd == "shell":
        return _run(["/bin/sh", *rest])

    print(f"unknown command: {cmd}\n", file=sys.stderr)
    print(HELP, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
