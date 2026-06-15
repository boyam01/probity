"""Deterministic public-claim audit for Probity launch docs.

This script is intentionally simple and conservative. It does not browse the
web and does not call an LLM. It checks that public-facing docs keep required
methodology/limit language and do not use forbidden claims in a positive
marketing context.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "README.md",
    "docs/METHODOLOGY.md",
    "docs/PUBLIC_CLAIMS.md",
    "docs/PROJECT_SURFACES.md",
    "docs/PUBLICATION_PREP.md",
    "docs/DISCOVERABILITY.md",
    "docs/DOCKER.md",
    "docs/QUICKSTART.md",
    "docs/RELATED_WORK.md",
]

PUBLIC_FILES = [
    "README.md",
    "docs/METHODOLOGY.md",
    "docs/PUBLIC_CLAIMS.md",
    "docs/PROJECT_SURFACES.md",
    "docs/PUBLICATION_PREP.md",
    "docs/DISCOVERABILITY.md",
    "docs/LAUNCH_COPY.md",
    "docs/DOCKER.md",
    "docs/QUICKSTART.md",
    "docs/USE_CASES.md",
    "docs/RELATED_WORK.md",
]

README_REQUIRED = [
    "Agent Reliability Methodology for False-Green Testing",
    "claim -> evidence -> repeated trials -> statistical verdict",
    "not a model leaderboard",
    "not an LLM judge",
    "not a proof of correctness",
    "does not prove arbitrary agent correctness",
    "does not detect all hallucinations",
    "does not rank models",
    "docs/METHODOLOGY.md",
    "docs/PUBLIC_CLAIMS.md",
    "docs/PROJECT_SURFACES.md",
    "docs/DISCOVERABILITY.md",
]

BANNED_PATTERNS = [
    r"\bworld'?s first\b",
    r"\bthe first\s+(?:agent|ai|coding|evaluation|reliability|false-green|tool|harness|methodology|project)\b",
    r"\bfirst\s+(?:agent|ai|coding|evaluation|reliability|false-green|tool|harness|methodology)\b",
    r"\bonly tool\b",
    r"\bthe only\b",
    r"\bunique\b",
    r"\bproof of correctness\b",
    r"\bproves correctness\b",
    r"\bprove correctness\b",
    r"\bproves agents do not lie\b",
    r"\bguarantees safe code\b",
    r"\bguarantees correctness\b",
    r"\bdetects all hallucinations\b",
    r"\bkills hallucinations\b",
    r"\beliminates hallucinations\b",
    r"\bbetter than AgentAssay\b",
    r"\bbeats AgentAssay\b",
    r"\bWilson-powered\b",
    r"\bAGI-grade\b",
]

ALLOWED_NEGATION_MARKERS = [
    "avoid",
    "block or downgrade",
    "do not",
    "does not",
    "cannot",
    "can't",
    "not ",
    "**not**",
    "not claimed",
    "not claim",
    "not a ",
    "never",
    "forbidden",
    "not allowed",
    "no ",
    "不得",
    "不是",
    "不宣稱",
    "不證明",
    "不保證",
    "不代表",
    "不要",
    "禁止",
]

ALLOWED_SECTION_MARKERS = [
    "avoid",
    "boundary",
    "forbidden",
    "not allowed",
    "not to say",
    "limits",
    "do not",
    "publication rule",
    "pre-publication",
]


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _line_allowed(line: str) -> bool:
    low = line.lower()
    if any(marker in low for marker in ALLOWED_NEGATION_MARKERS):
        return True
    stripped = low.strip()
    if stripped.startswith("- \"") or stripped.startswith("- '") or stripped.startswith("- `"):
        return True
    return False


def _check_required_files(errors: list[str]) -> None:
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).is_file():
            errors.append(f"missing required public doc: {rel}")


def _check_readme_required(errors: list[str]) -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    normalized = _norm_ws(text)
    for needle in README_REQUIRED:
        if _norm_ws(needle) not in normalized:
            errors.append(f"README missing required phrase/link: {needle}")


def _heading_text(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    return stripped.lstrip("#").strip().lower()


def _section_allowed(heading: str, advisory_block: bool) -> bool:
    if advisory_block:
        return True
    return any(marker in heading for marker in ALLOWED_SECTION_MARKERS)


def _check_banned_positive_claims(errors: list[str]) -> None:
    for rel in PUBLIC_FILES:
        path = ROOT / rel
        if not path.exists():
            continue
        current_heading = ""
        advisory_block = False
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            heading = _heading_text(line)
            if heading is not None:
                current_heading = heading
                advisory_block = False

            low = line.lower().strip()
            if (
                low.startswith("avoid:")
                or low.startswith("do not say:")
                or low.startswith("block or downgrade")
                or low.startswith("never claim")
                or low.startswith("not allowed")
            ):
                advisory_block = True

            allowed_context = _section_allowed(current_heading, advisory_block)
            for pat in BANNED_PATTERNS:
                if (
                    re.search(pat, line, flags=re.IGNORECASE)
                    and not allowed_context
                    and not _line_allowed(line)
                ):
                    errors.append(f"{rel}:{lineno}: forbidden claim context: {line.strip()}")


def _iter_markdown_links(text: str) -> list[str]:
    links = []
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
        target = match.group(1).strip()
        if not target:
            continue
        links.append(target)
    return links


def _check_local_links(errors: list[str]) -> None:
    for rel in PUBLIC_FILES:
        path = ROOT / rel
        if not path.exists():
            continue
        base = path.parent
        for target in _iter_markdown_links(path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#") or target.startswith("mailto:"):
                continue
            local = target.split("#", 1)[0]
            if not local:
                continue
            local_path = (base / local).resolve()
            try:
                local_path.relative_to(ROOT)
            except ValueError:
                errors.append(f"{rel}: link escapes repo: {target}")
                continue
            if not local_path.exists():
                errors.append(f"{rel}: broken local link: {target}")


def _check_docker_docs(errors: list[str]) -> None:
    pairs = [
        ("Dockerfile", "scripts/probity_docker_entry.py"),
        ("docs/DOCKER.md", "docker run --rm probity demo"),
        ("README.md", "docker build -t probity ."),
    ]
    for rel, needle in pairs:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if needle not in text:
            errors.append(f"{rel}: missing Docker proof string: {needle}")


def main() -> int:
    errors: list[str] = []
    _check_required_files(errors)
    _check_readme_required(errors)
    _check_banned_positive_claims(errors)
    _check_local_links(errors)
    _check_docker_docs(errors)

    if errors:
        print("PUBLIC CLAIM AUDIT: FAIL")
        for err in errors:
            print(f"- {err}")
        return 1

    print("PUBLIC CLAIM AUDIT: PASS")
    print(f"checked files: {len([p for p in PUBLIC_FILES if (ROOT / p).exists()])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
