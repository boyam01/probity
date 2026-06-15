"""Deterministic scripted agent, parameterized entirely by the task json (``agent.behavior``).

Behavior kinds (Phase 2 DoD):
- ``always_pass``                — run ``good`` actions every time
- ``bernoulli``  (p, seed)       — Random(seed).random() < p picks ``good`` else ``bad``
- ``drift``      (good_runs)     — internal run counter: first N runs ``good``, then ``bad``
- ``patch_script`` (per-seed)    — explicit per-seed action table, ``default`` fallback

Action ops (executed inside the isolated worktree):
- ``write_file``       {path, content}
- ``append_file``      {path, content}
- ``replace_in_file``  {path, old, new}
- ``delete_file``      {path}

Claim modes (§4.2 wire format, last line of final output):
- ``honest``         — "CLAIM: success" iff the script expects this run to succeed
- ``always_success`` / ``always_failure`` / ``none``
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from gauntlet.adapters.base import Adapter, AgentRunOutcome, AgentToolError
from gauntlet.types import TaskCase, TokenUsage, Trace


def _apply_action(workspace: Path, action: dict[str, Any]) -> None:
    op = action.get("op")
    path = workspace / action.get("path", "")
    if op == "write_file":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(action["content"], encoding="utf-8")
    elif op == "append_file":
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(action["content"])
    elif op == "replace_in_file":
        text = path.read_text(encoding="utf-8")
        if action["old"] not in text:
            raise AgentToolError(f"replace_in_file: pattern not found in {action.get('path')}")
        path.write_text(text.replace(action["old"], action["new"]), encoding="utf-8")
    elif op == "delete_file":
        path.unlink(missing_ok=True)
    else:
        raise AgentToolError(f"unknown scripted action op: {op!r}")


class ScriptedAgent(Adapter):
    """Replays a fully deterministic behavior script. Ground truth is therefore controlled."""

    def __init__(self, behavior: dict[str, Any], agent_id: str = "scripted-v1") -> None:
        self.behavior = behavior
        self.agent_id = agent_id
        self._run_counter = 0  # for "drift" behavior

    def config_dict(self) -> dict:
        return {"agent_id": self.agent_id, "behavior": self.behavior}

    # -- plan selection -----------------------------------------------------

    def _plan(self, seed: int) -> tuple[list[dict[str, Any]], bool]:
        """Return (actions, expect_success) for this run."""
        b = self.behavior
        kind = b.get("kind", "always_pass")
        good = b.get("good", {})
        bad = b.get("bad", {})
        if kind == "always_pass":
            plan = good or {"actions": b.get("actions", []), "expect_success": True}
            return list(plan.get("actions", [])), bool(plan.get("expect_success", True))
        if kind == "bernoulli":
            ok = random.Random(seed).random() < float(b["p"])
            plan = good if ok else bad
            return list(plan.get("actions", [])), bool(plan.get("expect_success", ok))
        if kind == "drift":
            ok = self._run_counter < int(b["good_runs"])
            plan = good if ok else bad
            return list(plan.get("actions", [])), bool(plan.get("expect_success", ok))
        if kind == "patch_script":
            runs = b.get("runs", {})
            plan = runs.get(str(seed), b.get("default", {}))
            return list(plan.get("actions", [])), bool(plan.get("expect_success", True))
        raise AgentToolError(f"unknown scripted behavior kind: {kind!r}")

    # -- execution ----------------------------------------------------------

    def run(self, workspace: Path, task: TaskCase, seed: int) -> AgentRunOutcome:
        actions, expect_success = self._plan(seed)
        self._run_counter += 1

        events: list[dict[str, Any]] = []
        for action in actions:
            _apply_action(workspace, action)
            events.append({"type": "action", **action})

        claim_mode = self.behavior.get("claim", "honest")
        if claim_mode == "honest":
            claim_line = "CLAIM: success" if expect_success else "CLAIM: failure"
        elif claim_mode == "always_success":
            claim_line = "CLAIM: success"
        elif claim_mode == "always_failure":
            claim_line = "CLAIM: failure"
        else:  # "none"
            claim_line = ""
        final_output = f"done.\n{claim_line}" if claim_line else "done."

        # Path-noise simulation (calibration R2): steps/latency fluctuate by seed,
        # and the noise is recorded in the trace so trace hashes differ run-to-run.
        if self.behavior.get("noisy_path"):
            steps = random.Random(seed).randint(8, 33)
            latency = round(random.Random(seed + 1000).uniform(0.4, 2.5), 3)
            events.append({"type": "path_noise", "steps": steps})
        else:
            steps = len(actions) + 1
            latency = float(self.behavior.get("latency_s", 0.0))

        return AgentRunOutcome(
            trace=Trace(events=events, final_output=final_output),
            steps=steps,
            tokens=TokenUsage(),
            cost_usd=float(self.behavior.get("cost_usd", 0.0)),
            latency_s=latency,
        )
