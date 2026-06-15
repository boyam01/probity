#!/usr/bin/env python3
"""Focus-loss contrast chart from FALSEPREMISE_CONTRAST.json — pure stdlib, hand-emitted SVG.

For each model with a clean neutral baseline (same semver fixture, neutral prompt at 2026-06-12),
draw its audited reliability under the NEUTRAL prompt vs under the FALSE-PREMISE prompt, annotated
with lies (false_claim) and test-tampering. The subject is the *within-model delta* caused purely
by swapping a neutral prompt for a confident false premise — i.e. focus-loss / sycophancy. Not a
model ranking.

    python scripts/make_focus_loss_chart.py reports/live/2026-06-14-falsepremise/FALSEPREMISE_CONTRAST.json out.svg
"""
import json
import sys
from pathlib import Path

GREY, AMBER, RED, INK, MUTE, GRID = "#8C8A82", "#BA7517", "#B23A2E", "#2C2C2A", "#5F5E5A", "#D3D1C7"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build(data: dict) -> str:
    paired = [r for r in data["confirmatory"] if r.get("has_neutral_baseline")]
    paired.sort(key=lambda r: r["fp_p_hat"])  # most-collapsed first
    n = len(paired)
    W, H = 760, 400
    ml, mr, mt, mb = 56, 16, 70, 104
    pw, ph = W - ml - mr, H - mt - mb
    group = pw / max(n, 1)
    bw = min(40, group / 2.8)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="system-ui,Segoe UI,sans-serif">']
    o.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
    o.append(f'<text x="{ml}" y="28" font-size="16" font-weight="500" fill="{INK}">Focus-loss under a confident false premise</text>')
    o.append(f'<text x="{ml}" y="46" font-size="11" fill="{MUTE}">Same semver fixture &amp; checker; only the prompt differs. Audited reliability p̂ over k=10: neutral prompt (grey) vs false-premise prompt (amber). Not a ranking.</text>')
    for pct in (0, 25, 50, 75, 100):
        y = mt + ph - ph * pct / 100
        o.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{W-mr}" y2="{y:.1f}" stroke="{GRID}" stroke-width="0.5"/>')
        o.append(f'<text x="{ml-8}" y="{y+3:.1f}" font-size="10" fill="{MUTE}" text-anchor="end">{pct}%</text>')
    for i, r in enumerate(paired):
        cx = ml + group * i + group / 2
        neutral = round(r["neutral_p_hat"] * 100)
        fp = round(r["fp_p_hat"] * 100)
        for j, (val, col) in enumerate([(neutral, GREY), (fp, AMBER)]):
            bx = cx - bw + j * bw
            bh = ph * val / 100
            by = mt + ph - bh
            o.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw-2:.1f}" height="{bh:.1f}" fill="{col}"/>')
            o.append(f'<text x="{bx+bw/2-1:.1f}" y="{by-4:.1f}" font-size="9.5" fill="{INK}" text-anchor="middle">{val}%</text>')
        # integrity tags below the model name
        tags = []
        dl = r.get("delta_lies", 0)
        if dl:
            tags.append(f"+{dl} lie" + ("s" if dl != 1 else ""))
        if r.get("fp_tamper"):
            tags.append(f"tamper×{r['fp_tamper']}")
        tagstr = "  ".join(tags) if tags else "honest"
        tagcol = RED if (r.get("fp_tamper") or dl >= 2) else MUTE
        o.append(f'<text x="{cx:.1f}" y="{mt+ph+18:.1f}" font-size="9.5" fill="{INK}" text-anchor="middle">{esc(r["model"])}</text>')
        o.append(f'<text x="{cx:.1f}" y="{mt+ph+33:.1f}" font-size="9" fill="{tagcol}" text-anchor="middle">{esc(tagstr)}</text>')
    o.append(f'<text x="{ml}" y="{H-10}" font-size="10" fill="{MUTE}">Confirmatory: complete 10-run models with a neutral baseline. deepseek-v4-pro collapsed 0.5→0.0 and edited the tests in 8/10 runs.</text>')
    o.append("</svg>")
    return "\n".join(o)


def main() -> int:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    Path(sys.argv[2]).write_text(build(data), encoding="utf-8", newline="\n")
    print("wrote", sys.argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
