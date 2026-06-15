"""Phase 3 DoD: the full calibration matrix must come back 10/10, FP=0, FN=0.

This runs the real pipeline end-to-end (worktrees, scripted agents, pytest
subprocesses) — it is the slowest test in the suite, by design.
"""
from pathlib import Path

from gauntlet.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_calibration_matrix_10_of_10(capsys, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    rc = main(["calibrate"])
    out = capsys.readouterr().out
    assert "matched 10/10" in out
    assert "FP=0" in out
    assert "FN=0" in out
    assert rc == 0
