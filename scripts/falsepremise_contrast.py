#!/usr/bin/env python3
"""False-premise focus-loss contrast — pure stdlib, zero LLM.

Pairs each model's NEUTRAL Python-semver session (2026-06-12, tasks/semver/task_semver_openai.json)
against its FALSE-PREMISE session (2026-06-14, tasks/semver/task_semver_falsepremise_openai.json).
Same fixture, same checker — only the prompt differs (the false-premise prompt confidently asserts
the correct tests are wrong and should be edited to match the buggy code). So the within-model
delta isolates the prompt's focus-loss effect: reliability drop and/or induced dishonesty
(false_claim) and test-tampering.

Pre-registered separation (see the session manifest):
  - CONFIRMATORY = models with a COMPLETE 10-run false-premise record in results.json.
  - EXPLORATORY  = incomplete models, summarized SEPARATELY from partial_results.jsonl and never
                   pooled into the confirmatory contrast or used to revise the headline.
"""
import json
import sys
from pathlib import Path

try:  # the report uses p̂ etc.; keep UTF-8 on consoles that default to a legacy codepage
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

LIVE = Path(__file__).resolve().parent.parent / "reports" / "live"
NEUTRAL = LIVE / "2026-06-12-semver-experiment" / "results.json"
FP = LIVE / "2026-06-14-falsepremise"


def _records(p: Path) -> dict:
    if not p.exists():
        return {}
    d = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for r in d.get("records", [d]):
        if "error" in r or "successes" not in r:
            continue
        out[r["model"]] = r
    return out


def _ig(r: dict, k: str) -> int:
    return r.get("integrity", {}).get(k, 0)


def build() -> dict:
    neutral = _records(NEUTRAL)
    fp = _records(FP / "results.json")

    confirmatory = []
    for model, fr in sorted(fp.items()):
        nr = neutral.get(model)
        row = {
            "model": model,
            "fp_p_hat": fr["p_hat"], "fp_verdict": fr["verdict"],
            "fp_lies": _ig(fr, "false_claim"), "fp_tamper": _ig(fr, "test_tampering"),
            "fp_scope": _ig(fr, "scope_violation"),
            "has_neutral_baseline": nr is not None,
        }
        if nr:
            row.update({
                "neutral_p_hat": nr["p_hat"], "neutral_verdict": nr["verdict"],
                "neutral_lies": _ig(nr, "false_claim"),
                "delta_p_hat": round(fr["p_hat"] - nr["p_hat"], 3),
                "delta_lies": _ig(fr, "false_claim") - _ig(nr, "false_claim"),
            })
        confirmatory.append(row)

    # exploratory: incomplete fp models, deduped by (model, run_index) keeping the latest attempt
    seen: dict = {}
    partial = FP / "partial_results.jsonl"
    if partial.exists():
        for line in partial.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if d["model"] in fp:  # already confirmatory-complete; not exploratory
                continue
            seen[(d["model"], d["run_index"])] = d
    explo: dict = {}
    for (m, _ri), d in seen.items():
        e = explo.setdefault(m, {"model": m, "runs": 0, "successes": 0, "lies": 0,
                                 "tamper": 0, "scope": 0})
        e["runs"] += 1
        e["successes"] += 1 if d.get("success") else 0
        e["lies"] += 1 if d.get("false_claim") else 0
        e["tamper"] += 1 if d.get("test_tampering") else 0
        e["scope"] += 1 if d.get("scope_violation") else 0

    return {"confirmatory": confirmatory, "exploratory": sorted(explo.values(), key=lambda x: x["model"])}


def to_markdown(data: dict) -> str:
    out = []
    out.append("#### Confirmatory contrast (complete 10-run false-premise models)\n")
    paired = [r for r in data["confirmatory"] if r["has_neutral_baseline"]]
    if paired:
        out.append("Same model, same semver fixture, neutral prompt → false-premise prompt:\n")
        out.append("| model | neutral p̂ / lies | false-premise p̂ / lies | Δp̂ | Δlies | tamper |")
        out.append("|---|---|---|---|---|---|")
        for r in paired:
            out.append(f"| {r['model']} | {r['neutral_p_hat']} / {r['neutral_lies']} | "
                       f"{r['fp_p_hat']} / {r['fp_lies']} | {r['delta_p_hat']:+} | "
                       f"{r['delta_lies']:+} | {r['fp_tamper']} |")
    unpaired = [r for r in data["confirmatory"] if not r["has_neutral_baseline"]]
    if unpaired:
        out.append("\nNo neutral same-task baseline (false-premise absolute only):\n")
        out.append("| model | false-premise p̂ | verdict | lies | tamper |")
        out.append("|---|---|---|---|---|")
        for r in unpaired:
            out.append(f"| {r['model']} | {r['fp_p_hat']} | {r['fp_verdict']} | {r['fp_lies']} | {r['fp_tamper']} |")
    out.append("\n#### Exploratory (incomplete — NOT in the confirmatory aggregate)\n")
    if data["exploratory"]:
        out.append("| model | runs done | successes | lies | tamper | scope |")
        out.append("|---|---|---|---|---|---|")
        for e in data["exploratory"]:
            out.append(f"| {e['model']} | {e['runs']}/10 | {e['successes']} | {e['lies']} | {e['tamper']} | {e['scope']} |")
    else:
        out.append("_(none)_")
    return "\n".join(out) + "\n"


def main() -> int:
    data = build()
    md = to_markdown(data)
    print(md)
    out = FP / "FALSEPREMISE_CONTRAST.json"
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
