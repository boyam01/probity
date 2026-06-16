"""Opt-in Docker sandbox adapter (A3, D-040): run each agent run inside a fresh, network-off
container for OS-level isolation and a full per-run reset.

This adapter is OPT-IN. The zero-dependency core never imports it at module load; ``make_adapter``
imports it lazily only when a task selects ``agent.adapter = "docker"`` — exactly as the subprocess
adapter needs the agent CLI, this one needs the ``docker`` CLI on PATH. The module itself uses only
the Python standard library.

Behavior (task json ``agent.behavior``):
- ``image``     : container image to run (required).
- ``cmd``       : argv inside the container; ``{prompt}`` and ``{seed}`` are substituted (required).
- ``network``   : value for ``docker run --network`` (default ``"none"`` → network-off).
- ``env``       : extra environment variables (merged over ``task.agent_input.env``).
- ``timeout_s`` : wall-clock limit (default 600) → AgentTimeout / failure_class "timeout".

The host worktree is bind-mounted at ``/work`` (the container working dir); container stdout becomes
the trace final output, so a trailing ``CLAIM: success`` line is parsed per §4.2.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from probity.adapters.base import Adapter, AgentRunOutcome, AgentTimeout, AgentToolError
from probity.types import TaskCase, TokenUsage, Trace


class DockerAgent(Adapter):
    def __init__(self, behavior: dict[str, Any], agent_id: str = "docker-v1") -> None:
        if not behavior.get("image"):
            raise ValueError("docker adapter requires behavior.image")
        if not behavior.get("cmd"):
            raise ValueError("docker adapter requires behavior.cmd")
        self.behavior = behavior
        self.agent_id = agent_id

    def config_dict(self) -> dict:
        return {"agent_id": self.agent_id, "behavior": self.behavior}

    def run(self, workspace: Path, task: TaskCase, seed: int) -> AgentRunOutcome:
        if shutil.which("docker") is None:
            raise AgentToolError("docker adapter selected but `docker` is not on PATH")
        subs = {"prompt": task.agent_input.prompt, "seed": str(seed)}
        inner = [a.format(**subs) for a in self.behavior["cmd"]]
        network = self.behavior.get("network", "none")
        env_pairs = dict(task.agent_input.env)
        env_pairs.update(self.behavior.get("env", {}))
        env_args: list[str] = []
        for key, value in env_pairs.items():
            env_args += ["-e", f"{key}={value}"]
        env_args += ["-e", f"PROBITY_SEED={seed}"]
        argv = [
            "docker", "run", "--rm", f"--network={network}",
            "-v", f"{workspace}:/work", "-w", "/work",
            *env_args, self.behavior["image"], *inner,
        ]
        timeout_s = float(self.behavior.get("timeout_s", 600))
        start = time.monotonic()
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired as e:
            raise AgentTimeout(f"docker agent exceeded {timeout_s}s") from e
        except OSError as e:
            raise AgentToolError(f"failed to launch docker: {e}") from e
        latency = time.monotonic() - start
        trace = Trace(
            events=[
                {
                    "type": "docker",
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
