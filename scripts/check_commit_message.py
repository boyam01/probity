#!/usr/bin/env python3
"""Lint a git commit message for shell-quoting accidents — pure stdlib, zero deps.

Motivation: writing a commit with a PowerShell here-string (@'...'@) under a POSIX shell
(or vice-versa) leaks the literal here-string markers into the message, producing a subject
like ``@`` with a trailing ``@`` line. This is a release-checklist guard, NOT a CI gate:

    git log -1 --pretty=%B | py -3.13 scripts/check_commit_message.py
    py -3.13 scripts/check_commit_message.py            # defaults to HEAD's message
    py -3.13 scripts/check_commit_message.py msg.txt    # lint a file

Exit 1 on a hard problem (a here-string marker leaked into the message); exit 0 otherwise,
printing soft warnings (e.g. overlong subject) without failing.
"""
import subprocess
import sys

# tokens that should never appear as a whole line / subject — they are shell here-string
# or quoting artifacts, not prose.
_MARKER_LINES = {"@", "@'", "'@", '@"', '"@', "EOF", "'EOF'"}
_MARKER_PREFIX = ("@'", '@"')
_MARKER_SUFFIX = ("'@", '"@')
_SUBJECT_MAX = 72


def _load_message(argv: list[str]) -> str:
    if len(argv) > 1:
        with open(argv[1], encoding="utf-8") as f:
            return f.read()
    if not sys.stdin.isatty():
        data = sys.stdin.read()
        if data.strip():
            return data
    return subprocess.run(
        ["git", "log", "-1", "--pretty=%B"], capture_output=True, text=True, check=True
    ).stdout


def lint(message: str) -> tuple[list[str], list[str]]:
    """Return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    lines = message.rstrip("\n").split("\n")
    subject = lines[0] if lines else ""

    if not subject.strip():
        errors.append("subject line is empty or whitespace-only")
    if subject.strip() in _MARKER_LINES:
        errors.append(f"subject is a stray shell/here-string marker: {subject.strip()!r}")
    if subject.startswith(_MARKER_PREFIX) or subject.endswith(_MARKER_SUFFIX):
        errors.append(f"subject begins/ends with a here-string marker: {subject!r}")

    for i, line in enumerate(lines):
        if line.strip() in _MARKER_LINES and not (i == 0 and subject.strip() not in _MARKER_LINES):
            errors.append(f"line {i + 1} is a stray here-string/quote marker: {line.strip()!r}")

    if len(subject) > _SUBJECT_MAX:
        warnings.append(f"subject is {len(subject)} chars (> {_SUBJECT_MAX}); consider shortening")

    # de-dup while preserving order
    errors = list(dict.fromkeys(errors))
    return errors, warnings


def main(argv: list[str]) -> int:
    message = _load_message(argv)
    errors, warnings = lint(message)
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        print("\ncommit message looks malformed -- check your shell quoting "
              "(here-strings: bash uses <<'EOF' ... EOF; PowerShell uses @'...'@).")
        return 1
    print("commit message OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
