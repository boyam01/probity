"""Dataclasses mirroring the frozen INTERFACE_CONTRACT.md (§2) schemas.

Wire formats (JSON) are byte-compatible with the frozen spec examples:
- ``tokens.in`` is a Python reserved word, stored as ``in_`` and mapped on (de)serialization (D-003).
- Optional extension fields (``agent``, ``env_fault``, ``checker.state_file`` etc., D-004)
  are omitted from JSON when unset, so the §2.1 example round-trips byte-identically.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

CHECKER_TYPES = ("pytest", "script", "state_file")
CRITICALITIES = ("standard", "safety_critical")
CRITICAL_RULE_TYPES = ("deleted_path", "modified_path")
FAILURE_CLASSES = (
    "wrong_final_state",
    "tool_error",
    "instruction_violation",
    "timeout",
    "crash",
    "destructive_action",
    "scope_violation",
    "test_tampering",
)
VERDICTS = ("PASS", "KILL", "INSUFFICIENT")


# ---------------------------------------------------------------------------
# §2.1 task_case.json
# ---------------------------------------------------------------------------

@dataclass
class WorkspaceSpec:
    type: str
    path: str
    pristine_ref: str = "HEAD"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "path": self.path, "pristine_ref": self.pristine_ref}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WorkspaceSpec":
        return cls(type=d["type"], path=d["path"], pristine_ref=d.get("pristine_ref", "HEAD"))


@dataclass
class AgentInput:
    prompt: str = ""
    env: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"prompt": self.prompt, "env": dict(self.env)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentInput":
        return cls(prompt=d.get("prompt", ""), env=dict(d.get("env", {})))


@dataclass
class CriticalRule:
    type: str  # "deleted_path" | "modified_path"
    glob: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "glob": self.glob}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CriticalRule":
        return cls(type=d["type"], glob=d["glob"])


@dataclass
class CheckerSpec:
    type: str  # "pytest" | "script" | "state_file"
    cmd: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    protected_paths: list[str] = field(default_factory=list)
    critical_rules: list[CriticalRule] = field(default_factory=list)
    # optional extensions (D-004) — omitted from JSON when unset
    state_file: str | None = None
    expected_content: str | None = None
    module: str | None = None
    # A2 (D-040): optional resource bounds on the checker subprocess. timeout_s is cross-platform;
    # max_memory_mb is enforced on POSIX (RLIMIT_AS) and best-effort (ignored) elsewhere.
    timeout_s: float | None = None
    max_memory_mb: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self.type,
            "cmd": list(self.cmd),
            "allowed_paths": list(self.allowed_paths),
            "protected_paths": list(self.protected_paths),
            "critical_rules": [r.to_dict() for r in self.critical_rules],
        }
        if self.state_file is not None:
            d["state_file"] = self.state_file
        if self.expected_content is not None:
            d["expected_content"] = self.expected_content
        if self.module is not None:
            d["module"] = self.module
        if self.timeout_s is not None:
            d["timeout_s"] = self.timeout_s
        if self.max_memory_mb is not None:
            d["max_memory_mb"] = self.max_memory_mb
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CheckerSpec":
        return cls(
            type=d["type"],
            cmd=list(d.get("cmd", [])),
            allowed_paths=list(d.get("allowed_paths", [])),
            protected_paths=list(d.get("protected_paths", [])),
            critical_rules=[CriticalRule.from_dict(r) for r in d.get("critical_rules", [])],
            state_file=d.get("state_file"),
            expected_content=d.get("expected_content"),
            module=d.get("module"),
            timeout_s=d.get("timeout_s"),
            max_memory_mb=d.get("max_memory_mb"),
        )


@dataclass
class SamplingSpec:
    seed_policy: str = "incremental"
    temperature: float | None = None
    # A-early-stop (D-041): opt-in. When True, the k-loop stops as soon as a deterministic KILL is
    # locked (test_tampering, or a critical event in a safety_critical task once k>=K_MIN). Default
    # False, omitted from JSON, so the frozen §2.1 example round-trips and calibration is unaffected.
    early_stop: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"seed_policy": self.seed_policy, "temperature": self.temperature}
        if self.early_stop:
            d["early_stop"] = True
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SamplingSpec":
        return cls(
            seed_policy=d.get("seed_policy", "incremental"),
            temperature=d.get("temperature"),
            early_stop=bool(d.get("early_stop", False)),
        )


@dataclass
class AgentSpec:
    """Optional extension (D-004): which adapter runs this task and how it behaves."""

    adapter: str = "scripted"
    agent_id: str = "scripted-v1"
    behavior: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"adapter": self.adapter, "agent_id": self.agent_id, "behavior": dict(self.behavior)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentSpec":
        return cls(
            adapter=d.get("adapter", "scripted"),
            agent_id=d.get("agent_id", "scripted-v1"),
            behavior=dict(d.get("behavior", {})),
        )


@dataclass
class TaskCase:
    task_id: str
    suite: str
    description: str
    workspace: WorkspaceSpec
    agent_input: AgentInput
    checker: CheckerSpec
    required_reliability: float
    criticality: str = "standard"
    k_planned: int = 10
    sampling: SamplingSpec = field(default_factory=SamplingSpec)
    # optional extensions (D-004)
    agent: AgentSpec | None = None
    env_fault: dict[str, Any] | None = None
    # A1 (D-040): declared environment preconditions — argv lists that must each exit 0
    # before the k runs; any failure surfaces as ENV_UNSTABLE (§3.1 rule 1), never KILL.
    env_preconditions: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "task_id": self.task_id,
            "suite": self.suite,
            "description": self.description,
            "workspace": self.workspace.to_dict(),
            "agent_input": self.agent_input.to_dict(),
            "checker": self.checker.to_dict(),
            "required_reliability": self.required_reliability,
            "criticality": self.criticality,
            "k_planned": self.k_planned,
            "sampling": self.sampling.to_dict(),
        }
        if self.agent is not None:
            d["agent"] = self.agent.to_dict()
        if self.env_fault is not None:
            d["env_fault"] = dict(self.env_fault)
        if self.env_preconditions:
            d["env_preconditions"] = [list(c) for c in self.env_preconditions]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TaskCase":
        return cls(
            task_id=d["task_id"],
            suite=d["suite"],
            description=d["description"],
            workspace=WorkspaceSpec.from_dict(d["workspace"]),
            agent_input=AgentInput.from_dict(d["agent_input"]),
            checker=CheckerSpec.from_dict(d["checker"]),
            required_reliability=d["required_reliability"],
            criticality=d.get("criticality", "standard"),
            k_planned=d.get("k_planned", 10),
            sampling=SamplingSpec.from_dict(d.get("sampling", {})),
            agent=AgentSpec.from_dict(d["agent"]) if "agent" in d else None,
            env_fault=d.get("env_fault"),
            env_preconditions=[list(c) for c in d.get("env_preconditions", [])],
        )

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "TaskCase":
        return cls.from_dict(json.loads(s))


# ---------------------------------------------------------------------------
# §2.2 run_result.json
# ---------------------------------------------------------------------------

@dataclass
class IntegrityFlags:
    false_claim: bool = False
    scope_violation: bool = False
    test_tampering: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "false_claim": self.false_claim,
            "scope_violation": self.scope_violation,
            "test_tampering": self.test_tampering,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IntegrityFlags":
        return cls(
            false_claim=d.get("false_claim", False),
            scope_violation=d.get("scope_violation", False),
            test_tampering=d.get("test_tampering", False),
        )


@dataclass
class CheckerOutput:
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "detail": self.detail}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CheckerOutput":
        return cls(passed=d["passed"], detail=d.get("detail", ""))


@dataclass
class TokenUsage:
    in_: int = 0  # JSON key "in" (reserved word in Python, D-003)
    out: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"in": self.in_, "out": self.out}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TokenUsage":
        return cls(in_=d.get("in", 0), out=d.get("out", 0))


@dataclass
class RunResult:
    task_id: str
    run_index: int
    agent_id: str
    agent_config_hash: str
    seed: int
    success: bool
    agent_claimed_success: bool | None
    failure_class: str | None
    integrity_flags: IntegrityFlags
    critical_event: bool
    checker_output: CheckerOutput
    modified_files: list[str]
    steps: int = 0
    tokens: TokenUsage = field(default_factory=TokenUsage)
    cost_usd: float = 0.0
    latency_s: float = 0.0
    trace_ref: str = ""
    # optional extension (D-004): sha256 of the trace, for DEGENERATE_VARIANCE (§3.5)
    trace_hash: str | None = None
    # optional extension: critical rule hit details, for audit_report.critical_events (§2.3)
    critical_hits: list["CriticalEventRecord"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "task_id": self.task_id,
            "run_index": self.run_index,
            "agent_id": self.agent_id,
            "agent_config_hash": self.agent_config_hash,
            "seed": self.seed,
            "success": self.success,
            "agent_claimed_success": self.agent_claimed_success,
            "failure_class": self.failure_class,
            "integrity_flags": self.integrity_flags.to_dict(),
            "critical_event": self.critical_event,
            "checker_output": self.checker_output.to_dict(),
            "modified_files": list(self.modified_files),
            "steps": self.steps,
            "tokens": self.tokens.to_dict(),
            "cost_usd": self.cost_usd,
            "latency_s": self.latency_s,
            "trace_ref": self.trace_ref,
        }
        if self.trace_hash is not None:
            d["trace_hash"] = self.trace_hash
        if self.critical_hits:
            d["critical_hits"] = [h.to_dict() for h in self.critical_hits]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RunResult":
        return cls(
            task_id=d["task_id"],
            run_index=d["run_index"],
            agent_id=d["agent_id"],
            agent_config_hash=d["agent_config_hash"],
            seed=d["seed"],
            success=d["success"],
            agent_claimed_success=d.get("agent_claimed_success"),
            failure_class=d.get("failure_class"),
            integrity_flags=IntegrityFlags.from_dict(d.get("integrity_flags", {})),
            critical_event=d.get("critical_event", False),
            checker_output=CheckerOutput.from_dict(d["checker_output"]),
            modified_files=list(d.get("modified_files", [])),
            steps=d.get("steps", 0),
            tokens=TokenUsage.from_dict(d.get("tokens", {})),
            cost_usd=d.get("cost_usd", 0.0),
            latency_s=d.get("latency_s", 0.0),
            trace_ref=d.get("trace_ref", ""),
            trace_hash=d.get("trace_hash"),
            critical_hits=[CriticalEventRecord.from_dict(h) for h in d.get("critical_hits", [])],
        )

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "RunResult":
        return cls.from_dict(json.loads(s))


# ---------------------------------------------------------------------------
# §2.3 audit_report.json
# ---------------------------------------------------------------------------

@dataclass
class CriticalEventRecord:
    run_index: int
    rule: str  # e.g. "deleted_path:**"
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {"run_index": self.run_index, "rule": self.rule, "path": self.path}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CriticalEventRecord":
        return cls(run_index=d["run_index"], rule=d["rule"], path=d["path"])


@dataclass
class FailureCluster:
    class_: str  # JSON key "class"
    count: int
    example_run: int

    def to_dict(self) -> dict[str, Any]:
        return {"class": self.class_, "count": self.count, "example_run": self.example_run}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FailureCluster":
        return cls(class_=d["class"], count=d["count"], example_run=d["example_run"])


@dataclass
class MeanCV:
    mean: float = 0.0
    cv: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"mean": self.mean, "cv": self.cv}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MeanCV":
        return cls(mean=d.get("mean", 0.0), cv=d.get("cv", 0.0))


@dataclass
class IntegritySummary:
    false_claim: int = 0
    scope_violation: int = 0
    test_tampering: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "false_claim": self.false_claim,
            "scope_violation": self.scope_violation,
            "test_tampering": self.test_tampering,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IntegritySummary":
        return cls(
            false_claim=d.get("false_claim", 0),
            scope_violation=d.get("scope_violation", 0),
            test_tampering=d.get("test_tampering", 0),
        )


@dataclass
class TaskAudit:
    task_id: str
    k: int
    successes: int
    p_hat: float
    wilson_95: list[float]  # [lo, hi]
    pass_hat_k: float
    pass_k_lower: float
    verdict: str
    reason_codes: list[str]
    diagnostics: list[str]
    integrity_summary: IntegritySummary
    critical_events: list[CriticalEventRecord]
    failure_clusters: list[FailureCluster]
    cost: MeanCV
    latency_s: MeanCV
    k_needed_estimate: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "k": self.k,
            "successes": self.successes,
            "p_hat": self.p_hat,
            "wilson_95": list(self.wilson_95),
            "pass_hat_k": self.pass_hat_k,
            "pass_k_lower": self.pass_k_lower,
            "verdict": self.verdict,
            "reason_codes": list(self.reason_codes),
            "diagnostics": list(self.diagnostics),
            "integrity_summary": self.integrity_summary.to_dict(),
            "critical_events": [e.to_dict() for e in self.critical_events],
            "failure_clusters": [c.to_dict() for c in self.failure_clusters],
            "cost": self.cost.to_dict(),
            "latency_s": self.latency_s.to_dict(),
            "k_needed_estimate": self.k_needed_estimate,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TaskAudit":
        return cls(
            task_id=d["task_id"],
            k=d["k"],
            successes=d["successes"],
            p_hat=d["p_hat"],
            wilson_95=list(d["wilson_95"]),
            pass_hat_k=d["pass_hat_k"],
            pass_k_lower=d["pass_k_lower"],
            verdict=d["verdict"],
            reason_codes=list(d.get("reason_codes", [])),
            diagnostics=list(d.get("diagnostics", [])),
            integrity_summary=IntegritySummary.from_dict(d.get("integrity_summary", {})),
            critical_events=[CriticalEventRecord.from_dict(e) for e in d.get("critical_events", [])],
            failure_clusters=[FailureCluster.from_dict(c) for c in d.get("failure_clusters", [])],
            cost=MeanCV.from_dict(d.get("cost", {})),
            latency_s=MeanCV.from_dict(d.get("latency_s", {})),
            k_needed_estimate=d.get("k_needed_estimate"),
        )


@dataclass
class EnvStatus:
    canary_pre_ok: bool = True
    canary_post_ok: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"canary_pre_ok": self.canary_pre_ok, "canary_post_ok": self.canary_post_ok}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EnvStatus":
        return cls(
            canary_pre_ok=d.get("canary_pre_ok", True),
            canary_post_ok=d.get("canary_post_ok", True),
        )


@dataclass
class AuditReport:
    harness_version: str
    spec_hash: str
    env: EnvStatus
    tasks: list[TaskAudit]
    suite_verdict: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "harness_version": self.harness_version,
            "spec_hash": self.spec_hash,
            "env": self.env.to_dict(),
            "tasks": [t.to_dict() for t in self.tasks],
            "suite_verdict": self.suite_verdict,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AuditReport":
        return cls(
            harness_version=d["harness_version"],
            spec_hash=d["spec_hash"],
            env=EnvStatus.from_dict(d.get("env", {})),
            tasks=[TaskAudit.from_dict(t) for t in d.get("tasks", [])],
            suite_verdict=d["suite_verdict"],
        )

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "AuditReport":
        return cls.from_dict(json.loads(s))


# ---------------------------------------------------------------------------
# §4.1 runtime types: Trace / CheckResult
# ---------------------------------------------------------------------------

@dataclass
class Trace:
    """A deterministic record of one agent run: structured events + final text output."""

    events: list[dict[str, Any]] = field(default_factory=list)
    final_output: str = ""

    def sha256(self) -> str:
        canonical = json.dumps(
            {"events": self.events, "final_output": self.final_output},
            sort_keys=True,
            ensure_ascii=False,
        )
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_jsonl(self) -> str:
        lines = [json.dumps(e, ensure_ascii=False) for e in self.events]
        lines.append(json.dumps({"type": "final_output", "text": self.final_output}, ensure_ascii=False))
        return "\n".join(lines) + "\n"

    @classmethod
    def from_jsonl(cls, s: str) -> "Trace":
        events: list[dict[str, Any]] = []
        final_output = ""
        for line in s.splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("type") == "final_output":
                final_output = obj.get("text", "")
            else:
                events.append(obj)
        return cls(events=events, final_output=final_output)


@dataclass
class CheckResult:
    """Frozen §4.1 contract: passed, failure_class, integrity_flags, critical_event, detail, modified_files."""

    passed: bool
    failure_class: str | None
    integrity_flags: IntegrityFlags
    critical_event: bool
    detail: str
    modified_files: list[str]
    # detail records for critical rule hits (feeds audit_report.critical_events)
    critical_hits: list[CriticalEventRecord] = field(default_factory=list)
