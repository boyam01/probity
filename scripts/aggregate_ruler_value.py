#!/usr/bin/env python3
"""Aggregate the with-ruler vs without-ruler decision quality across every published live
session. Pure stdlib, zero LLM — reads each reports/live/*/results.json.

The "without ruler" baseline is the naive single-run shipper: they run the agent once and ship
if that run either passed the checker OR the agent self-claimed success. Over k runs the chance
a single run ships the agent is:

    naive_ship_rate = (successes + false_claim) / k

(every passing run ships; every failing run that *claimed* success also ships — that is exactly
the false_claim count). The "with ruler" call is the frozen verdict.
"""
import json
from pathlib import Path

LIVE = Path(__file__).resolve().parent.parent / "reports" / "live"


def sessions():
    for rj in sorted(LIVE.glob("*/results.json")):
        data = json.loads(rj.read_text(encoding="utf-8"))
        recs = data.get("records") or [data]
        for r in recs:
            if "error" in r or "successes" not in r:
                continue
            k = r["k"]
            fc = r.get("integrity", {}).get("false_claim", 0)
            yield {
                "batch": rj.parent.name,
                "model": r["model"],
                "k": k,
                "successes": r["successes"],
                "p_hat": r["p_hat"],
                "verdict": r["verdict"],
                "false_claim": fc,
                "naive_ship_rate": round((r["successes"] + fc) / k, 3),
                "verifier_ok": r.get("verifier_ok"),
            }


def main():
    s = list(sessions())
    n = len(s)
    total_runs = sum(x["k"] for x in s)
    mean_naive = round(sum(x["naive_ship_rate"] for x in s) / n, 3) if n else 0
    passed = sum(1 for x in s if x["verdict"] == "PASS")
    killed = sum(1 for x in s if x["verdict"] == "KILL")
    insuf = sum(1 for x in s if x["verdict"] == "INSUFFICIENT")
    total_lies = sum(x["false_claim"] for x in s)
    # the agents a single run would most likely have shipped (naive_ship_rate >= 0.5) yet the
    # ruler did NOT pass:
    naive_would_ship = [x for x in s if x["naive_ship_rate"] >= 0.5]
    ruler_refused = [x for x in naive_would_ship if x["verdict"] != "PASS"]
    verifier_all = all(x["verifier_ok"] for x in s if x["verifier_ok"] is not None)

    print(f"sessions={n}  total_runs={total_runs}  verifier_all_passed={verifier_all}")
    print(f"mean naive single-run ship probability = {mean_naive:.0%}")
    print(f"ruler verdicts:  PASS={passed}  KILL={killed}  INSUFFICIENT={insuf}")
    print(f"false-claim incidents (lies invisible to a single run) = {total_lies}")
    print(f"sessions a single run would likely ship (rate>=50%) = {len(naive_would_ship)}; "
          f"of those the ruler refused to PASS = {len(ruler_refused)} "
          f"({len(ruler_refused)}/{len(naive_would_ship)})")
    print()
    print(f"{'batch':<32}{'model':<20}{'naive_ship':<12}{'audited':<9}{'verdict':<14}{'lies'}")
    print("-" * 100)
    for x in sorted(s, key=lambda z: (z["batch"], -z["naive_ship_rate"])):
        print(f"{x['batch']:<32}{x['model']:<20}{x['naive_ship_rate']:<12.0%}{x['p_hat']:<9}{x['verdict']:<14}{x['false_claim']}")

    out = LIVE / "AGGREGATE_ruler_vs_noruler.json"
    out.write_text(json.dumps({
        "sessions": n, "total_runs": total_runs, "verifier_all_passed": verifier_all,
        "mean_naive_ship_rate": mean_naive,
        "verdicts": {"PASS": passed, "KILL": killed, "INSUFFICIENT": insuf},
        "false_claim_incidents": total_lies,
        "naive_would_ship": len(naive_would_ship),
        "ruler_refused_of_those": len(ruler_refused),
        "rows": s,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
