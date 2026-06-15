#!/usr/bin/env python3
"""CLI SUT launcher — LIVE_AUDIT_SPEC v0.2 §A5. Pure plumbing, NOT an agent.

This is a thin, portable launcher that the EXISTING subprocess adapter calls to invoke an
external coding-agent CLI (Codex CLI / Claude Code CLI) as the system under test. It contains
ZERO patching logic: the CLI does all reading/editing inside the worktree. The launcher only:
  - reads the task prompt from a file (so the prompt never goes on a command line — avoids
    Windows .cmd quoting hell),
  - feeds it to the CLI via stdin,
  - runs the CLI with worktree-scoped write permission (§A5: auto-approve limited to worktree),
  - forwards the CLI's stdout (becomes the trace) and exit code.

Because it does no patching, it is NOT the "built-in agent" — §7.4 (built-in agent ≤ 1, =
agents/llm_patch_agent.py) is unaffected (DECISION_LOG D-031).

Invocation (by the subprocess adapter, cwd = worktree):
    python agents/cli_sut_runner.py --tool {codex,claude} --model <model> --prompt-file <file>

Exit codes: passthrough from the CLI. The checker judges the resulting worktree state; this
launcher never decides success.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path


def build_command(tool: str, model: str, cwd: str) -> list[str]:
    """Return the shell command string parts for the CLI. Prompt is fed via stdin (the
    trailing '-' / stdin convention), never on the command line."""
    if tool == "codex":
        # codex exec reads instructions from stdin when '-' is given (prevents the non-interactive
        # hang); workspace-write keeps edits inside the worktree; approval=never runs autonomously;
        # minimal reasoning effort is the "lower-tier" knob for the ChatGPT-account model.
        # 'minimal' is rejected by codex when image_gen/web_search tools are enabled; 'low'
        # is the lowest compatible effort (still the lower-tier knob on gpt-5.4).
        effort = os.environ.get("GAUNTLET_CODEX_EFFORT", "low")
        return [
            "codex", "exec",
            "-m", model,
            "-c", f"model_reasoning_effort={effort}",
            "-c", "approval_policy=never",
            "-s", "workspace-write",
            "--skip-git-repo-check",
            "-C", cwd,
            "-",
        ]
    if tool == "claude":
        # claude -p = headless print mode; acceptEdits auto-approves edits within the cwd
        # worktree. The prompt is piped on stdin.
        return [
            "claude", "-p",
            "--model", model,
            "--permission-mode", "acceptEdits",
        ]
    raise SystemExit(f"unknown CLI tool: {tool!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", required=True, choices=["codex", "claude"])
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt-file", required=True)
    args = ap.parse_args()

    cwd = os.getcwd()
    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    parts = build_command(args.tool, args.model, cwd)
    # Quote each part for the shell; the prompt is NOT here (it goes via stdin).
    cmdline = " ".join(_q(p) for p in parts)

    # shell=True so Windows npm .cmd shims resolve via PATH; prompt via stdin avoids quoting.
    proc = subprocess.run(
        cmdline,
        cwd=cwd,
        input=prompt,
        text=True,
        shell=True,
        capture_output=True,
    )
    # stdout becomes the trace final_output; surface stderr tail for debugging.
    sys.stdout.write(proc.stdout or "")
    if proc.stderr:
        sys.stderr.write(proc.stderr[-2000:])
    return proc.returncode


def _q(s: str) -> str:
    if not s or any(c in s for c in ' "\t'):
        return '"' + s.replace('"', '\\"') + '"'
    return s


if __name__ == "__main__":
    sys.exit(main())
