"""A1 (D-040): declared task env_preconditions. A failed precondition is an environment
fault → INSUFFICIENT [ENV_UNSTABLE] via the frozen §3.1 rule-1 path; decide() is unchanged.
Optional field: absent → omitted from JSON → the frozen §2.1 example still round-trips."""
from probity.runner import ensure_git_workspace, run_env_preconditions, run_suite
from probity.types import (
    AgentInput,
    AgentSpec,
    CheckerSpec,
    SamplingSpec,
    TaskCase,
    WorkspaceSpec,
)
from probity.verdict import decide


def _task(ws_rel: str, preconds: list[list[str]]) -> TaskCase:
    return TaskCase(
        task_id="precond_demo",
        suite="test",
        description="env precondition probe",
        workspace=WorkspaceSpec(type="git", path=ws_rel, pristine_ref="HEAD"),
        agent_input=AgentInput(prompt="write the state file"),
        checker=CheckerSpec(
            type="state_file",
            allowed_paths=["state.json"],
            state_file="state.json",
            expected_content="ok",
        ),
        required_reliability=0.5,
        criticality="standard",
        k_planned=5,
        sampling=SamplingSpec(),
        agent=AgentSpec(
            adapter="scripted",
            agent_id="t",
            behavior={
                "kind": "always_pass",
                "claim": "honest",
                "good": {
                    "actions": [{"op": "write_file", "path": "state.json", "content": "ok"}],
                    "expect_success": True,
                },
            },
        ),
        env_preconditions=preconds,
    )


def test_preconditions_all_pass(tmp_path):
    t = _task("x", [["python", "-c", "import sys; sys.exit(0)"]])
    assert run_env_preconditions(t, tmp_path) is True


def test_precondition_nonzero_fails(tmp_path):
    t = _task("x", [["python", "-c", "import sys; sys.exit(3)"]])
    assert run_env_preconditions(t, tmp_path) is False


def test_precondition_unlaunchable_fails(tmp_path):
    t = _task("x", [["this-binary-does-not-exist-xyz"]])
    assert run_env_preconditions(t, tmp_path) is False


def test_no_preconditions_field_omitted_from_json():
    t = _task("x", [])
    assert "env_preconditions" not in t.to_dict()
    # round-trips byte-stably through the dataclasses
    assert TaskCase.from_json(t.to_json()).to_dict() == t.to_dict()


def test_failing_precondition_yields_env_unstable(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "README.txt").write_text("x\n", encoding="utf-8")
    ensure_git_workspace(ws)
    t = _task(str(ws), [["python", "-c", "import sys; sys.exit(1)"]])
    data = run_suite([t], repo_root=tmp_path, traces_root=tmp_path / "traces")
    assert data.env.canary_pre_ok is False
    audit = decide(t, data.results[t.task_id], data.env)
    assert audit.verdict == "INSUFFICIENT"
    assert audit.reason_codes == ["ENV_UNSTABLE"]


def test_passing_precondition_does_not_force_env_unstable(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "README.txt").write_text("x\n", encoding="utf-8")
    ensure_git_workspace(ws)
    t = _task(str(ws), [["python", "-c", "import sys; sys.exit(0)"]])
    data = run_suite([t], repo_root=tmp_path, traces_root=tmp_path / "traces")
    assert data.env.canary_pre_ok is True
