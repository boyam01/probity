"""Generic CLI agent adapter: run an arbitrary command inside the isolated worktree.

Behavior (task json ``agent.behavior``):
- ``cmd``: list of argv strings. Substituted template variables:
  ``{prompt}`` (task prompt text), ``{seed}``, ``{workspace}`` (worktree path),
  ``{repo_root}`` (the launch cwd, so scripts living in the main repo can be addressed),
  ``{prompt_file}`` (path to a temp file containing the prompt — for agents that take a
  prompt file instead of an inline argument; deleted after the run).
- ``env``: extra environment variables (merged over task.agent_input.env).
- ``timeout_s``: wall-clock limit (default 600) → AgentTimeout / failure_class "timeout".

``cmd[0]`` of ``python``/``python3`` is replaced with the harness interpreter (D-008).
stdout becomes the trace final output (so a trailing ``CLAIM: success`` line is parsed per §4.2).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from probity.adapters.base import Adapter, AgentRunOutcome, AgentTimeout, AgentToolError
from probity.types import TaskCase, TokenUsage, Trace


class SubprocessAgent(Adapter):
    def __init__(self, behavior: dict[str, Any], agent_id: str = "subprocess-v1") -> None:
        if not behavior.get("cmd"):
            raise ValueError("subprocess adapter requires behavior.cmd")
        self.behavior = behavior
        self.agent_id = agent_id

    def config_dict(self) -> dict:
        return {"agent_id": self.agent_id, "behavior": self.behavior}

    def run(self, workspace: Path, task: TaskCase, seed: int) -> AgentRunOutcome:
        prompt_file: str | None = None
        if any("{prompt_file}" in a for a in self.behavior["cmd"]):
            fd, prompt_file = tempfile.mkstemp(prefix="probity_prompt_", suffix=".txt", text=True)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(task.agent_input.prompt)
        subs = {
            "prompt": task.agent_input.prompt,
            "seed": str(seed),
            "workspace": str(workspace),
            "repo_root": str(Path.cwd()),
            "prompt_file": prompt_file or "",
        }
        argv = [a.format(**subs) for a in self.behavior["cmd"]]
        if argv and argv[0] in ("python", "python3"):
            argv[0] = sys.executable
        env = dict(os.environ)
        env.update(task.agent_input.env)
        env.update(self.behavior.get("env", {}))
        env["GAUNTLET_SEED"] = str(seed)
        timeout_s = float(self.behavior.get("timeout_s", 600))

        start = time.monotonic()
        try:
            proc = subprocess.run(
                argv,
                cwd=workspace,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as e:
            raise AgentTimeout(f"agent exceeded {timeout_s}s") from e
        except OSError as e:
            raise AgentToolError(f"failed to launch agent: {e}") from e
        finally:
            if prompt_file:
                try:
                    os.unlink(prompt_file)
                except OSError:
                    pass
        latency = time.monotonic() - start

        trace = Trace(
            events=[
                {
                    "type": "subprocess",
                    "cmd": argv,
                    "returncode": proc.returncode,
                    "stderr_tail": proc.stderr[-2000:],
                }
            ],
            final_output=proc.stdout,
        )
        return AgentRunOutcome(
            trace=trace,
            steps=1,
            tokens=TokenUsage(),
            cost_usd=0.0,
            latency_s=round(latency, 3),
        )
