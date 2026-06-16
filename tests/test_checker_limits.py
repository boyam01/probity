"""A2 (D-040): optional checker resource bounds. timeout_s is cross-platform; max_memory_mb is
POSIX-only (RLIMIT_AS). Optional fields omit-when-unset so the frozen §2.1 example round-trips."""
import os
import sys

import pytest

from probity.checker import run_pytest_detail
from probity.types import CheckerSpec


def test_checker_timeout_fails_a_hung_command(tmp_path):
    passed, detail = run_pytest_detail(
        tmp_path, [sys.executable, "-c", "import time; time.sleep(5)"], timeout=1
    )
    assert passed is False
    assert "timeout" in detail.lower()


def test_checker_passes_fast_command(tmp_path):
    passed, _ = run_pytest_detail(
        tmp_path, [sys.executable, "-c", "import sys; sys.exit(0)"], timeout=30
    )
    assert passed is True


@pytest.mark.skipif(os.name != "posix", reason="RLIMIT_AS memory cap is POSIX-only")
def test_checker_memory_cap_fails_oversized_program(tmp_path):
    # allocate ~400MB under a 64MB cap → RLIMIT_AS makes it fail (non-zero exit)
    passed, _ = run_pytest_detail(
        tmp_path,
        [sys.executable, "-c", "x = bytearray(400 * 1024 * 1024); print(len(x))"],
        timeout=30,
        max_memory_mb=64,
    )
    assert passed is False


def test_checker_limits_round_trip():
    spec = CheckerSpec(
        type="pytest", cmd=["python", "-m", "pytest"], timeout_s=30.0, max_memory_mb=256
    )
    d = spec.to_dict()
    assert d["timeout_s"] == 30.0 and d["max_memory_mb"] == 256
    assert CheckerSpec.from_dict(d).to_dict() == d


def test_checker_limits_omitted_when_unset():
    d = CheckerSpec(type="pytest", cmd=["python", "-m", "pytest"]).to_dict()
    assert "timeout_s" not in d and "max_memory_mb" not in d
