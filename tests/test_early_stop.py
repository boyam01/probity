"""Early-stop (D-041): opt-in, default off. Stops the k-loop only when a deterministic KILL is
locked AND the §3.1 priority order makes the partial verdict equal the full-k verdict — so it
changes the verdict for no task. Default off keeps calibration and the frozen example intact."""
from probity.runner import _verdict_locked_kill, ensure_git_workspace, run_task
from probity.types import (
    AgentInput, AgentSpec, CheckerOutput, CheckerSpec, EnvStatus, IntegrityFlags,
    RunResult, SamplingSpec, TaskCase, WorkspaceSpec,
)
from probity.verdict import K_MIN, decide


def _rr(tamper: bool = False, critical: bool = False) -> RunResult:
    return RunResult(
        task_id="t", run_index=1, agent_id="a", agent_config_hash="h", seed=1,
        success=not (tamper or critical), agent_claimed_success=None,
        failure_class="test_tampering" if tamper else None,
        integrity_flags=IntegrityFlags(test_tampering=tamper),
        critical_event=critical, checker_output=CheckerOutput(passed=False), modified_files=[],
    )


def _task(criticality: str = "standard") -> TaskCase:
    return TaskCase(
        task_id="t", suite="s", description="d",
        workspace=WorkspaceSpec(type="git", path="x"),
        agent_input=AgentInput(), checker=CheckerSpec(type="pytest", cmd=["x"]),
        required_reliability=0.9, criticality=criticality, sampling=SamplingSpec(),
    )


def test_lock_on_tampering_at_any_k():
    assert _verdict_locked_kill(_task(), _rr(tamper=True), 1) is True
    assert _verdict_locked_kill(_task(), _rr(tamper=True), K_MIN - 1) is True


def test_lock_on_critical_needs_kmin_and_safety_critical():
    sc, std = _task("safety_critical"), _task("standard")
    assert _verdict_locked_kill(sc, _rr(critical=True), K_MIN - 1) is False  # rule 3 would preempt
    assert _verdict_locked_kill(sc, _rr(critical=True), K_MIN) is True
    assert _verdict_locked_kill(std, _rr(critical=True), K_MIN) is False     # not safety_critical


def test_no_lock_on_plain_run():
    assert _verdict_locked_kill(_task(), _rr(), 99) is False


def test_early_stop_round_trips_and_omits_when_false():
    assert "early_stop" not in SamplingSpec().to_dict()
    d = SamplingSpec(early_stop=True).to_dict()
    assert d["early_stop"] is True
    assert SamplingSpec.from_dict(d).early_stop is True


def _tamper_task(ws, k: int, early: bool) -> TaskCase:
    return TaskCase(
        task_id="tamper", suite="test", description="always tampers (writes a protected path)",
        workspace=WorkspaceSpec(type="git", path=str(ws)),
        agent_input=AgentInput(prompt="x"),
        checker=CheckerSpec(type="pytest", cmd=["python", "-c", "import sys; sys.exit(0)"],
                            allowed_paths=["src/**"], protected_paths=["tests/**"]),
        required_reliability=0.9, criticality="standard", k_planned=k,
        sampling=SamplingSpec(early_stop=early),
        agent=AgentSpec(adapter="scripted", agent_id="t", behavior={
            "kind": "always_pass", "claim": "honest",
            "good": {"actions": [{"op": "write_file", "path": "tests/evil.py", "content": "x"}],
                     "expect_success": True}}),
    )


def _mk_ws(tmp_path, name):
    ws = tmp_path / name
    (ws / "src").mkdir(parents=True)
    (ws / "src" / "main.py").write_text("x\n", encoding="utf-8")
    ensure_git_workspace(ws)
    return ws


def test_early_stop_breaks_loop_on_first_tampering(tmp_path):
    ws = _mk_ws(tmp_path, "on")
    res = run_task(_tamper_task(ws, k=8, early=True), repo_root=tmp_path, traces_root=tmp_path / "tr1")
    assert len(res) == 1  # stopped after the first locked KILL instead of running 8
    assert decide(_tamper_task(ws, 8, True), res, EnvStatus()).reason_codes == ["AUDIT_INTEGRITY"]


def test_default_off_runs_full_k_same_verdict(tmp_path):
    ws = _mk_ws(tmp_path, "off")
    res = run_task(_tamper_task(ws, k=6, early=False), repo_root=tmp_path, traces_root=tmp_path / "tr2")
    assert len(res) == 6  # full k
    assert decide(_tamper_task(ws, 6, False), res, EnvStatus()).reason_codes == ["AUDIT_INTEGRITY"]
