"""Audit the public export surface.

The working repository may retain private evidence, governance history, and
research reports. The public export should ship the tool, examples, and
usage/methodology docs only. This script computes that export set by excluding
known-private paths, then checks links and secret-like tokens.
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_ANYWHERE_PATTERNS = [
    ".env",
    ".env.*",
    "*.env",
    "*.key",
    "*.pem",
    "*secret*",
]

ALLOWED_TRACKED_EXCEPTIONS = {
    "reports/.gitkeep",
}

SECRET_REGEXES = [
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        r"\b(?:OPENAI|ANTHROPIC)_API_KEY\s*=\s*(?!os\.getenv\b)(?![\"']?\$)(?![\"']?(?:xxx|your|dummy|mock|example|test|<|\.\.\.))[^ \n\"']{16,}",
        re.IGNORECASE,
    ),
]

TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".html",
    ".ini",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".rs",
    ".sh",
    ".svg",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}


def _git_lines(*args: str) -> list[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return [line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()]


def _is_forbidden_tracked(path: str) -> bool:
    if path in ALLOWED_TRACKED_EXCEPTIONS:
        return False
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in FORBIDDEN_ANYWHERE_PATTERNS)


def _is_public_release_file(path: str) -> bool:
    if path in ALLOWED_TRACKED_EXCEPTIONS:
        return True
    return not any(fnmatch.fnmatchcase(path, pattern) for pattern in _export_ignore_patterns())


def _export_ignore_patterns() -> list[str]:
    attrs = ROOT / ".gitattributes"
    if not attrs.is_file():
        return []
    patterns: list[str] = []
    for raw in attrs.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and "export-ignore" in parts[1:]:
            pattern = parts[0].replace("\\", "/")
            patterns.append(pattern)
            if pattern.endswith("/**"):
                patterns.append(pattern[:-3] + "/*")
            elif pattern.endswith("/"):
                patterns.append(pattern + "*")
    return patterns


def _looks_like_text(path: str) -> bool:
    return Path(path).suffix.lower() in TEXT_SUFFIXES


def _check_forbidden_paths(errors: list[str], paths: list[str]) -> None:
    for path in paths:
        if _is_forbidden_tracked(path):
            errors.append(f"forbidden file path: {path}")


def _check_secret_strings(errors: list[str], release_files: list[str]) -> None:
    for rel in release_files:
        if not _looks_like_text(rel):
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for regex in SECRET_REGEXES:
            if regex.search(text):
                errors.append(f"possible secret-like token in tracked file: {rel}")


def _iter_markdown_links(text: str) -> list[str]:
    links: list[str] = []
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
        target = match.group(1).strip()
        if target:
            links.append(target)
    return links


def _check_markdown_links(errors: list[str], release_files: list[str]) -> None:
    release_set = set(release_files)
    for rel in release_files:
        if Path(rel).suffix.lower() != ".md":
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for target in _iter_markdown_links(text):
            if "://" in target or target.startswith("#") or target.startswith("mailto:"):
                continue
            local = target.split("#", 1)[0]
            if not local:
                continue
            local_path = (path.parent / local).resolve()
            try:
                rel_target = local_path.relative_to(ROOT).as_posix()
            except ValueError:
                errors.append(f"{rel}: local link escapes repo: {target}")
                continue
            if rel_target not in release_set:
                errors.append(f"{rel}: local link target is not in release file set: {target}")


def main() -> int:
    errors: list[str] = []
    tracked = _git_lines("ls-files")
    untracked = _git_lines("ls-files", "--others", "--exclude-standard")
    candidate_files = sorted(set(tracked + untracked))
    release_files = [path for path in candidate_files if _is_public_release_file(path)]
    excluded_count = len(candidate_files) - len(release_files)

    _check_forbidden_paths(errors, candidate_files)
    _check_secret_strings(errors, release_files)
    _check_markdown_links(errors, release_files)

    if errors:
        print("PUBLIC EXPORT AUDIT: FAIL")
        for err in errors:
            print(f"- {err}")
        return 1

    print("PUBLIC EXPORT AUDIT: PASS")
    print(f"candidate files: {len(candidate_files)}")
    print(f"public export files checked: {len(release_files)}")
    print(f"private/research files excluded from export: {excluded_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
