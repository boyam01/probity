"""Failure clustering — pure rule-based counting by failure_class. Zero LLM."""
from __future__ import annotations

from probity.types import FailureCluster, RunResult


def failure_clusters(results: list[RunResult]) -> list[FailureCluster]:
    """Group failed runs by failure_class; largest cluster first, ties by class name."""
    counts: dict[str, int] = {}
    examples: dict[str, int] = {}
    for r in results:
        if r.success or r.failure_class is None:
            continue
        counts[r.failure_class] = counts.get(r.failure_class, 0) + 1
        examples.setdefault(r.failure_class, r.run_index)
    return [
        FailureCluster(class_=cls, count=n, example_run=examples[cls])
        for cls, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
