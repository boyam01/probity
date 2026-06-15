# Project surfaces

Probity has three different surfaces. Keep them separate.

## 1. Source repository

The source repository is the canonical working repo. It keeps:

- core tool code under `gauntlet/`;
- task schema and frozen interface docs;
- calibration fixtures and demo fixtures;
- governance and decision history;
- recorded evidence under `reports/live/`;
- research and review notes.

Do not delete or untrack source-repo evidence just to make the public package
smaller.

## 2. Public tool export

The public export is what a first-time user should receive when they only need
the ruler:

- Python package and CLI code;
- demo and calibration tasks;
- README, quickstart, Docker docs, methodology docs, and related-work notes;
- Dockerfile and compose file;
- public claim and publication checklists.

It excludes private/raw research surfaces:

- `reports/**`;
- `DECISION_LOG.md`, `CLAUDE.md`, `AGENTS.md`, kickoff and live-audit specs;
- private comparison/effectiveness/external-review reports;
- local experimental sidecars.

The export boundary is enforced by:

- `.gitattributes` `export-ignore` rules;
- `scripts/audit_public_release.py`;
- `make release-audit`;
- `make public-archive`.

## 3. Local experiments

Experimental sidecars may exist locally while the method is still being
validated. They should not become part of the public tool export unless promoted
through an explicit Owner decision and a separate review.

Examples:

- hidden-holdout task experiments;
- market-value audit experiments;
- generated charts or ad hoc reports.

## Rule of thumb

If it teaches a user how to install and run the ruler, it belongs in the public
export. If it is raw evidence, model-session output, governance history, or a
private research report, keep it in the source repo but out of the public export.
