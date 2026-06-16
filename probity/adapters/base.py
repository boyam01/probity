"""Adapter contract: run an agent once inside an isolated workspace, return a Trace."""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from probity.types import TaskCase, TokenUsage, Trace


class AgentExecutionError(Exception):
    """Agent-side failure during a run. ``failure_class`` is the §2.2 primary cause."""

    failure_class = "crash"


class AgentTimeout(AgentExecutionError):
    failure_class = "timeout"


class AgentToolError(AgentExecutionError):
    failure_class = "tool_error"


@dataclass
class AgentRunOutcome:
    trace: Trace
    steps: int = 0
    tokens: TokenUsage = field(default_factory=TokenUsage)
    cost_usd: float = 0.0
    latency_s: float = 0.0


class Adapter(ABC):
    """One adapter instance is reused for all k runs of a task (it may keep run-counter state)."""

    agent_id: str = "agent"

    @abstractmethod
    def run(self, workspace: Path, task: TaskCase, seed: int) -> AgentRunOutcome:
        """Execute the agent once inside ``workspace``. Must be deterministic given (task, seed, run order)."""

    def config_hash(self) -> str:
        canonical = json.dumps(self.config_dict(), sort_keys=True, ensure_ascii=False)
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def config_dict(self) -> dict:
        return {"agent_id": self.agent_id}
