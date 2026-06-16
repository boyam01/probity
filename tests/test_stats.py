"""Phase 1: §3.3 numeric ground truth (±1e-3), k_needed gates, monotonicity property."""
import pytest

from probity.stats import (
    k_needed,
    k_needed_estimate,
    mean_cv,
    pass_hat_k,
    pass_k_lower,
    wilson_ci,
)

TOL = 1e-3

# §3.3 frozen ground truth (n=10)
GROUND_TRUTH = [
    (10, 10, 0.7225, 1.0000),
    (9, 10, 0.5958, 0.9821),
    (8, 10, 0.4902, 0.9433),
    (7, 10, 0.3968, 0.8922),
    (6, 10, 0.3127, 0.8318),
    (5, 10, 0.2366, 0.7634),
    (2, 10, 0.0567, 0.5098),
]


@pytest.mark.parametrize("s,n,exp_lo,exp_hi", GROUND_TRUTH)
def test_wilson_ground_truth(s, n, exp_lo, exp_hi):
    lo, hi = wilson_ci(s, n)
    assert lo == pytest.approx(exp_lo, abs=TOL)
    assert hi == pytest.approx(exp_hi, abs=TOL)


@pytest.mark.parametrize("r,expected", [(0.80, 16), (0.90, 35), (0.95, 73)])
def test_k_needed_frozen_gates(r, expected):
    assert k_needed(r) == expected


def test_wilson_lo_monotone_in_successes():
    """Property (Phase 1 DoD): for fixed n, wilson_lo is non-decreasing in successes."""
    for n in range(1, 101):
        prev_lo = -1.0
        for s in range(0, n + 1):
            lo, _ = wilson_ci(s, n)
            assert lo >= prev_lo - 1e-12, f"lo not monotone at s={s}, n={n}"
            prev_lo = lo


def test_wilson_hi_monotone_in_successes():
    for n in range(1, 101):
        prev_hi = -1.0
        for s in range(0, n + 1):
            _, hi = wilson_ci(s, n)
            assert hi >= prev_hi - 1e-12, f"hi not monotone at s={s}, n={n}"
            prev_hi = hi


def test_wilson_bounds_within_unit_interval():
    for n in (1, 5, 10, 50):
        for s in range(0, n + 1):
            lo, hi = wilson_ci(s, n)
            assert 0.0 <= lo <= hi <= 1.0


def test_wilson_invalid_inputs():
    with pytest.raises(ValueError):
        wilson_ci(1, 0)
    with pytest.raises(ValueError):
        wilson_ci(-1, 10)
    with pytest.raises(ValueError):
        wilson_ci(11, 10)


def test_pass_hat_k_definition():
    # §2.3 example: p_hat=0.70, k=10 → 0.0282
    assert pass_hat_k(0.70, 10) == pytest.approx(0.0282, abs=TOL)


def test_pass_k_lower_definition():
    lo, _ = wilson_ci(7, 10)
    # §2.3 example: 0.3968^10 ≈ 0.0001
    assert pass_k_lower(lo, 10) == pytest.approx(0.0001, abs=TOL)


def test_mean_cv_basic():
    m, cv = mean_cv([1.0, 1.0, 1.0])
    assert m == 1.0
    assert cv == 0.0
    m, cv = mean_cv([1.0, 3.0])
    assert m == 2.0
    assert cv == pytest.approx(0.5)


def test_mean_cv_empty_and_zero_mean():
    assert mean_cv([]) == (0.0, 0.0)
    assert mean_cv([0.0, 0.0]) == (0.0, 0.0)


def test_k_needed_estimate_all_success_matches_k_needed():
    """10/10 vs r=0.90 (calibration B2): estimate must be 35, agreeing with k_needed."""
    assert k_needed_estimate(10, 10, 0.90, 10) == 35
    assert k_needed(0.90) == 35


def test_k_needed_estimate_unreachable_at_observed_rate():
    """§3.4: p̂ <= r → None. Calibration B1: 8/10 vs r=0.80."""
    assert k_needed_estimate(8, 10, 0.80, 10) is None
    assert k_needed_estimate(5, 10, 0.90, 10) is None


def test_k_needed_estimate_respects_cap():
    """r so close to p̂ that no n within 10×k_planned suffices → None."""
    assert k_needed_estimate(99, 100, 0.9899, 10) is None
