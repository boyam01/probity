# Quickstart

Try Probity locally in a few minutes. No API keys are required for the demo,
calibration, or test suite.

Probity is the public-facing name. The Python package/import path is still
`probity`.

## Option A — Docker

```bash
git clone https://github.com/boyam01/probity.git
cd probity
docker build -t probity .
docker run --rm probity demo-once
docker run --rm probity demo
```

`demo-once` shows the single run that looks shippable. `demo` repeats the same
task and shows why one green is not enough. The demo's KILL verdict is expected.

Run the gates:

```bash
docker run --rm probity calibrate
docker run --rm probity test
```

Run your own task:

```bash
docker run --rm -v "$PWD:/work" probity run /work/path/to/task_case.json
```

PowerShell:

```powershell
docker run --rm -v "${PWD}:/work" probity run /work/path/to/task_case.json
```

More: [DOCKER.md](DOCKER.md).

## Option B — local Python

Requirements:

- Python >= 3.11;
- system `git`;
- `pytest` for the built-in tests/checkers.

```bash
python -m pip install pytest
python -m probity run demo/patchbot/task_demo_patchbot_01.json --once --seed 1
python -m probity run demo/patchbot/task_demo_patchbot_01.json
python -m probity calibrate
python -m pytest -q
```

On this Windows development machine, use `py -3.13` if plain `python` resolves
to an older interpreter.

## The three outcomes

- **KILL** — the evidence refutes the reliability claim or shows an integrity
  failure. The demo intentionally reaches `KILL [RELIABILITY_REFUTED]`.
- **PASS** — no falsification was found under the registered battery. This is
  not proof of correctness.
- **INSUFFICIENT** — the evidence is underpowered or the environment is
  unstable. A flawless 10/10 record is still insufficient for a 0.90 claim.

## What to read next

- What Probity is good for: [USE_CASES.md](USE_CASES.md)
- Methodology: [METHODOLOGY.md](METHODOLOGY.md)
- Docker details: [DOCKER.md](DOCKER.md)
- What a report contains: [EVIDENCE_BUNDLE.md](EVIDENCE_BUNDLE.md)
- Public claim boundaries: [PUBLIC_CLAIMS.md](PUBLIC_CLAIMS.md)

## Agent CLI choices

Probity can run any bounded CLI agent command through the subprocess adapter.
Good starting options are:

- Codex CLI: <https://github.com/openai/codex>
- Claude Code: <https://code.claude.com/>

Use local Python rather than Docker when the agent CLI is installed on your
host and must be reachable from the subprocess command.
