"""Custom `script` checker (LIVE_AUDIT_SPEC §2.1 enum; D-035): run `cargo test` in the Rust
workspace and pass iff it exits 0. Deterministic, zero LLM.

The frozen check() in gauntlet/checker.py runs assert_protected / assert_scope /
apply_critical_rules (integrity, by git-diff paths — language-agnostic) BEFORE calling this;
this module only decides the final-state pass/fail. A non-compiling edit → cargo exit != 0 →
False → wrong_final_state (a real low-tier failure mode, fairly caught)."""
import os
import subprocess


def check(workspace, trace, task) -> bool:
    env = dict(os.environ)
    try:
        proc = subprocess.run(
            ["cargo", "test", "--quiet"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False
