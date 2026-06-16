"""Frozen §3.2-§3.4 statistics: Wilson CI, pass^k, mean/cv, k_needed.

Pure stdlib, fully deterministic. z is frozen at 1.96 (§3.2).
"""
from __future__ import annotations

import math

Z = 1.96  # frozen (§3.2)


def wilson_ci(successes: int, n: int, z: float = Z) -> tuple[float, float]:
    """95% Wilson score interval per the frozen §3.2 formulas."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= successes <= n:
        raise ValueError("successes must be within [0, n]")
    p_hat = successes / n
    denom = 1 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
    lo = max(0.0, center - half)
    hi = min(1.0, center + half)
    return lo, hi


def pass_hat_k(p_hat: float, k: int) -> float:
    """pass_hat_k = p̂^k (§2.3)."""
    return p_hat**k


def pass_k_lower(wilson_lo: float, k: int) -> float:
    """pass_k_lower = wilson_lo^k (§2.3)."""
    return wilson_lo**k


def mean_cv(values: list[float]) -> tuple[float, float]:
    """Mean and coefficient of variation (population std / mean; 0.0 when mean is 0)."""
    if not values:
        return 0.0, 0.0
    m = sum(values) / len(values)
    if m == 0:
        return m, 0.0
    var = sum((v - m) ** 2 for v in values) / len(values)
    return m, math.sqrt(var) / m


def k_needed(r: float, z: float = Z) -> int:
    """Minimum consecutive all-success runs to PASS claim r: ceil(r·z²/(1-r)) (§3.3)."""
    if not 0 < r < 1:
        raise ValueError("r must be in (0, 1)")
    return math.ceil(r * z * z / (1 - r))


def k_needed_estimate(successes: int, k: int, r: float, k_planned: int) -> int | None:
    """§3.4: smallest n > k such that wilson_lo(round(p̂·n), n) >= r.

    Returns None when p̂ <= r (unreachable at observed rate) or when the search
    exceeds the cap of 10 × k_planned.
    """
    if k <= 0:
        return None
    p_hat = successes / k
    if p_hat <= r:
        return None
    cap = 10 * k_planned
    n = k + 1
    while n <= cap:
        s = round(p_hat * n)
        s = min(s, n)
        lo, _ = wilson_ci(s, n)
        if lo >= r:
            return n
        n += 1
    return None
