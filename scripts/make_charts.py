#!/usr/bin/env python3
"""Generate committable SVG 'ruler value-add' charts from an experiment results.json.

Per session: naive single-run impression (run #1 passed = 100%, failed = 0%) vs probity-audited
reliability (p_hat). The chart's subject is the RULER's correction, shown in run order — it is
NOT a quality ranking (§A4.2; Owner-approved amendment D-036). Pure stdlib; hand-emitted SVG so
it renders on GitHub with no dependency.

    python scripts/make_charts.py <results.json> <out.svg> "Title"
"""
import json
import sys
from pathlib import Path

AMBER, TEAL, INK, MUTE, GRID = "#BA7517", "#1D9E75", "#2C2C2A", "#5F5E5A", "#D3D1C7"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build(records, title):
    rows = [r for r in records if "error" not in r]
    n = len(rows)
    W, H = 720, 380
    ml, mr, mt, mb = 56, 16, 64, 96
    pw, ph = W - ml - mr, H - mt - mb
    group = pw / max(n, 1)
    bw = min(46, group / 2.6)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="system-ui,Segoe UI,sans-serif">']
    out.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
    out.append(f'<text x="{ml}" y="28" font-size="16" font-weight="500" fill="{INK}">{esc(title)}</text>')
    out.append(f'<text x="{ml}" y="46" font-size="11" fill="{MUTE}">naive single-run (amber) vs probity-audited reliability over k=10 (teal). Run order; not a model ranking.</text>')
    for pct in (0, 25, 50, 75, 100):
        y = mt + ph - ph * pct / 100
        out.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{W-mr}" y2="{y:.1f}" stroke="{GRID}" stroke-width="0.5"/>')
        out.append(f'<text x="{ml-8}" y="{y+3:.1f}" font-size="10" fill="{MUTE}" text-anchor="end">{pct}%</text>')
    for i, r in enumerate(rows):
        cx = ml + group * i + group / 2
        naive = 100 if r["naive"]["run1_success"] else 0
        aud = round(r["p_hat"] * 100)
        for j, (val, col) in enumerate([(naive, AMBER), (aud, TEAL)]):
            bx = cx - bw + j * bw
            bh = ph * val / 100
            by = mt + ph - bh
            out.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw-2:.1f}" height="{bh:.1f}" fill="{col}"/>')
            if j == 1:
                out.append(f'<text x="{bx+bw/2-1:.1f}" y="{by-4:.1f}" font-size="10" fill="{INK}" text-anchor="middle">{aud}%</text>')
        verdict = "KILL" if r["verdict"] == "KILL" else ("PASS" if r["verdict"] == "PASS" else "INSUF")
        fc = r["integrity"]["false_claim"]
        tag = f"{verdict}" + (f" lie×{fc}" if fc else "")
        out.append(f'<text x="{cx:.1f}" y="{mt+ph+16:.1f}" font-size="10" fill="{INK}" text-anchor="middle" font-weight="500">{esc(tag)}</text>')
        out.append(f'<text x="{cx:.1f}" y="{mt+ph+32:.1f}" font-size="9.5" fill="{MUTE}" text-anchor="middle">{esc(r["model"])}</text>')
    out.append(f'<text x="{ml}" y="{H-8}" font-size="10" fill="{MUTE}">All runs published, zero selection. Independent trace verifier passed for every session.</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    results = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    records = results.get("records") or [results]  # single-session files have no 'records'
    Path(sys.argv[2]).write_text(build(records, sys.argv[3]), encoding="utf-8", newline="\n")
    print("wrote", sys.argv[2], f"({len([r for r in records if 'error' not in r])} sessions)")


if __name__ == "__main__":
    main()
