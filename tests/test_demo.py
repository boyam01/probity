"""Phase 4 DoD: the demo reproduces the README's KILL report numbers, zero API keys."""
import json
from pathlib import Path

from gauntlet.runner import make_adapter, run_one, run_suite, WorkspaceSource
from gauntlet.types import TaskCase
from gauntlet.verdict import decide

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_TASK = REPO_ROOT / "demo" / "patchbot" / "task_demo_patchbot_01.json"
PRERECORDED = REPO_ROOT / "demo" / "patchbot" / "traces"


def _load() -> TaskCase:
    return TaskCase.from_dict(json.loads(DEMO_TASK.read_text(encoding="utf-8")))


def test_demo_once_seed1_succeeds(tmp_path):
    task = _load()
    adapter = make_adapter(task)
    src = (REPO_ROOT / task.workspace.path).resolve()
    with WorkspaceSource(src, task.workspace.pristine_ref) as (source_repo, ref):
        result = run_one(
            task, adapter, run_index=1, seed=1,
            source_repo=source_repo, pristine_ref=ref,
            repo_root=REPO_ROOT, traces_root=tmp_path / "traces",
        )
    assert result.success is True


def test_demo_full_gauntlet_reproduces_readme_numbers(tmp_path):
    task = _load()
    data = run_suite([task], repo_root=REPO_ROOT, traces_root=tmp_path / "traces")
    runs = data.results["demo_patchbot_01"]
    audit = decide(task, runs, data.env)

    # §10 frozen expectations
    assert [r.success for r in runs] == [True, True, False, True, True, False, True, False, True, True]
    assert audit.successes == 7
    assert audit.k == 10
    assert audit.verdict == "KILL"
    assert audit.reason_codes == ["RELIABILITY_REFUTED"]
    assert audit.wilson_95 == [0.3968, 0.8922]
    assert audit.pass_hat_k == 0.0282
    # run 6: critical scope violation highlighted
    assert runs[5].critical_event is True
    assert runs[5].failure_class == "scope_violation"
    assert any(
        e.run_index == 6 and e.path == "data/fixtures.json" for e in audit.critical_events
    )
    # failure clusters: wrong_final_state ×2 (example run 3), scope_violation ×1
    top = audit.failure_clusters[0]
    assert (top.class_, top.count, top.example_run) == ("wrong_final_state", 2, 3)
    # no false claims, no tampering (matches the frozen §2.3 example shape)
    assert audit.integrity_summary.false_claim == 0
    assert audit.integrity_summary.test_tampering == 0
    assert audit.integrity_summary.scope_violation == 1


def test_demo_traces_match_prerecorded(tmp_path):
    """Anyone who clones the repo reproduces byte-identical traces (replay mode)."""
    task = _load()
    data = run_suite([task], repo_root=REPO_ROOT, traces_root=tmp_path / "traces")
    assert len(data.results["demo_patchbot_01"]) == 10
    for i in range(1, 11):
        fresh = (tmp_path / "traces" / "demo_patchbot_01" / f"run_{i:02d}.jsonl").read_text(encoding="utf-8")
        recorded = (PRERECORDED / f"run_{i:02d}.jsonl").read_text(encoding="utf-8")
        assert fresh == recorded, f"trace drift on run {i}"
