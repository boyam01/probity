# Publication prep

This repo is prepared for a future public launch, but publishing still requires
explicit Owner approval in the current conversation.

## Hard gates

- Do not push.
- Do not create a public GitHub repo or organization.
- Do not change repository visibility.
- Do not publish to PyPI or any package registry.
- Do not claim the `probity` package name is reserved or owned.
- Keep the Python package/import path as `gauntlet` unless Owner explicitly
  approves a rename.
- Do not publish private research reports, raw traces, model-session logs, API
  keys, local `.env` files, or benchmark artifacts.
- Do not delete or untrack source-repo evidence just to make the public package
  smaller. Use the public export boundary instead.

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

## GitHub organization / repo checklist

Recommended shape:

- create a clean GitHub organization rather than using a crowded personal page;
- choose a name that does not imply package-name ownership;
- create the repo private first;
- push only the tool, public usage docs, and methodology docs;
- keep `reports/` and private research docs out of the public export;
- keep the source repository evidence and governance history intact unless
  Owner explicitly approves a separate archival move;
- push only after docs, Docker smoke, calibration, tests, and public export audit pass;
- turn public only after final Owner approval.

Suggested repo descriptions:

- `Agent reliability methodology for false-green testing of AI coding agents.`
- `Evidence-based reliability testing for AI coding agents.`
- `Claim -> evidence -> verdict for coding-agent reliability audits.`

Suggested topics:

`ai-agents`, `coding-agents`, `agent-evaluation`, `agent-reliability`,
`llmops`, `software-testing`, `ci`, `test-automation`, `developer-tools`,
`deterministic-testing`, `reliability-testing`, `false-green`, `ai-safety`,
`provenance`, `audit`, `docker`.

Social preview:

- image size: 1280x640 PNG;
- text: `Probity`, `Agent reliability methodology`, `False-green testing for AI coding agents`;
- use a solid background so it works across platforms.

## Pre-launch verification

Run:

```bash
docker build -t probity .
docker run --rm probity demo-once
docker run --rm probity demo
docker run --rm probity calibrate
docker run --rm probity test
python -m pytest -q
python -m gauntlet calibrate
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
- `README.md` for over-specific or overconfident claims.

Before any public package or archive, verify the public export excludes
`reports/`, secret files, and private research-report docs. The
`audit_public_release.py` gate checks the export boundary without deleting
source-repo evidence.

## Forum launch path

Start with feedback-oriented posts:

- "I built a false-green testing methodology for coding agents. What failure modes am I
  missing?"
- "How do you stop coding agents from editing tests or claiming success before
  the checker passes?"
- "Can you break this agent reliability methodology?"

Ask for critique on:

- verdict semantics;
- task schema;
- Docker quickstart;
- evidence bundle;
- missing competitors / prior art;
- real false-green cases people have seen.

Do not lead with valuation, model superiority, or broad safety claims.
