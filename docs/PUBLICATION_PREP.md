# Release hygiene and export boundary

Probity is public. This document is the standing release-hygiene checklist: what
stays out of the public tree, the language to avoid, and the gates to run before
every update. It is not a claim that the project is unreleased.

## Ongoing discipline (regardless of visibility)

- The public tree ships the tool, examples, and methodology/usage docs only.
- Private research reports, raw traces, model-session logs, API keys, local
  `.env` files, and benchmark artifacts stay in the source repository. The export
  boundary is enforced by `.gitattributes` (`export-ignore`) and checked by
  `scripts/audit_public_release.py`; it does not delete source-repo evidence.
- Do not claim the `probity` package name is reserved or owned on any registry.
- Frozen behaviour (schema §2, verdict §3, checker §4) changes only through a
  `DECISION_LOG.md` amendment that keeps calibration 10/10 with zero per-case
  patches.

## Public positioning

Use:

- agent reliability methodology;
- false-green testing for AI coding agents;
- evidence-gated CI for coding agents;
- false-green integrity gate;
- claim -> evidence -> verdict;
- deterministic checker;
- zero-LLM built-in verdict path;
- PASS means "no falsification found under this registered battery."

Avoid:

- first / only / unique;
- proves correctness;
- guarantees safe code;
- detects all hallucinations;
- kills hallucinations;
- better than AgentAssay or any named project;
- Wilson as novelty;
- model leaderboard framing.

## Repository presentation

Description (pick one):

- `Agent reliability methodology for false-green testing of AI coding agents.`
- `Evidence-based reliability testing for AI coding agents.`
- `Claim -> evidence -> verdict for coding-agent reliability audits.`

Topics:

`ai-agents`, `coding-agents`, `agent-evaluation`, `agent-reliability`,
`llmops`, `software-testing`, `ci`, `test-automation`, `developer-tools`,
`deterministic-testing`, `reliability-testing`, `false-green`, `ai-safety`,
`provenance`, `audit`, `docker`.

Social preview:

- image size: 1280x640 PNG;
- text: `Probity`, `Agent reliability methodology`, `False-green testing for AI coding agents`;
- use a solid background so it works across platforms.

## Gates to run before every public update

```bash
docker build -t probity .
docker run --rm probity demo-once
docker run --rm probity demo
docker run --rm probity calibrate
docker run --rm probity test
python -m pytest -q
python -m probity calibrate
python scripts/audit_public_claims.py
python scripts/audit_public_release.py
```

Review:

- `docs/PUBLIC_CLAIMS.md` for allowed / boundary / not-allowed claims;
- `docs/METHODOLOGY.md` for the core method framing;
- `docs/PROJECT_SURFACES.md` for source repo vs public export boundaries;
- `docs/RELATED_WORK.md` for stale or unverifiable claims;
- `docs/LAUNCH_COPY.md` for banned language;
- `docs/DOCKER.md` for install friction;
- `docs/DISCOVERABILITY.md` for GitHub topics, repo description, README title, and social preview;
- `docs/ROADMAP.md` for what is deferred and why;
- `README.md` for over-specific or overconfident claims.

Before publishing any package or archive, verify the public export excludes
`reports/`, secret files, and private research-report docs. The
`audit_public_release.py` gate checks the export boundary without deleting
source-repo evidence.

## Feedback path

Useful, feedback-oriented framings:

- "I built a false-green testing methodology for coding agents. What failure modes am I
  missing?"
- "How do you stop coding agents from editing tests or claiming success before
  the checker passes?"
- "Can you break this agent reliability methodology?"

Ask for critique on verdict semantics, task schema, the Docker quickstart, the
evidence bundle, missing prior art, and real false-green cases people have seen.
Do not lead with valuation, model superiority, or broad safety claims.
