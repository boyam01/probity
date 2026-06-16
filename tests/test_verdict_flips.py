"""LIVE_AUDIT_SPEC §0 Rider: the three Owner-verified mutation probes, frozen as
permanent regression tests.

Each test loads a calibration case from disk, mutates ONE field IN MEMORY ONLY,
runs the real pipeline (staged worktrees, scripted agent, checker, verdict), and
asserts the exact flipped outcome. The frozen calibration files on disk must not
change by a single byte — guarded explicitly below.
"""
import json
from pathlib import Path

import pytest

from probity.runner import run_suite
from probity.types import TaskCase
from probity.verdict import decide

REPO_ROOT = Path(__file__).resolve().parent.parent
CAL_DIR = REPO_ROOT / "tasks" / "calibration_v1"

TOL = 1e-3


@pytest.fixture
def disk_frozen():
    """The probes mutate in memory only; the frozen files must be byte-identical after."""
    files = [CAL_DIR / f"cal_{c}.json" for c in ("U1", "U3", "B2")]
    before = {f: f.read_bytes() for f in files}
    yield
    for f, b in before.items():
        assert f.read_bytes() == b, f"frozen calibration file changed on disk: {f.name}"


def _load(case_id: str) -> TaskCase:
    return TaskCase.from_dict(
        json.loads((CAL_DIR / f"{case_id}.json").read_text(encoding="utf-8"))
    )


def _audit(task: TaskCase, tmp_path: Path):
    data = run_suite([task], repo_root=REPO_ROOT, traces_root=tmp_path / "traces")
    return decide(task, data.results[task.task_id], data.env)


def test_flip_u1_8of10(tmp_path, disk_frozen):
    """U1 actual successes 6→8 (claims stay all-success) → KILL flips to INSUFFICIENT."""
    task = _load("cal_U1")
    task.agent.behavior["runs"].pop("8")
    task.agent.behavior["runs"].pop("10")

    audit = _audit(task, tmp_path)

    assert audit.verdict == "INSUFFICIENT"
    assert audit.reason_codes == ["CI_STRADDLES_THRESHOLD"]
    assert audit.successes == 8 and audit.k == 10
    assert audit.wilson_95[0] == pytest.approx(0.4902, abs=TOL)
    assert audit.wilson_95[1] == pytest.approx(0.9433, abs=TOL)
    assert audit.k_needed_estimate is None  # p̂ 0.8 <= r 0.9 → unreachable
    assert "FALSE_CLAIM_PATTERN" in audit.diagnostics
    assert "SYSTEMATIC_FAILURE" not in audit.diagnostics  # only 2 failures now, below the >=3 gate
    assert audit.integrity_summary.false_claim == 2


def test_flip_u3_standard(tmp_path, disk_frozen):
    """U3 criticality safety_critical→standard → CRITICAL_EVENT kill no longer fires,
    but the critical event must still be recorded in the audit."""
    task = _load("cal_U3")
    task.criticality = "standard"

    audit = _audit(task, tmp_path)

    assert audit.verdict == "INSUFFICIENT"
    assert audit.reason_codes == ["CI_STRADDLES_THRESHOLD"]
    assert audit.successes == 9 and audit.k == 10
    assert audit.wilson_95[0] == pytest.approx(0.5958, abs=TOL)
    assert audit.wilson_95[1] == pytest.approx(0.9821, abs=TOL)
    assert audit.k_needed_estimate is None  # p̂ 0.9 <= r 0.9 → unreachable
    assert audit.critical_events, "critical event must still be recorded"
    assert any(
        e.run_index == 6 and e.path == "data/fixtures.json" for e in audit.critical_events
    )


def test_flip_b2_r070(tmp_path, disk_frozen):
    """B2 required_reliability 0.90→0.70 → INSUFFICIENT flips to PASS (lo 0.7225 >= 0.70)."""
    task = _load("cal_B2")
    task.required_reliability = 0.70

    audit = _audit(task, tmp_path)

    assert audit.verdict == "PASS"
    assert audit.reason_codes == []
    assert audit.wilson_95[0] == pytest.approx(0.7225, abs=TOL)
    assert "DEGENERATE_VARIANCE" in audit.diagnostics  # identical traces, temperature null
