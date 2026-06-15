# Docker quickstart

Docker is the easiest way to try Probity locally without installing Python
packages on the host.

No API keys are required for the built-in demo, calibration, or tests.

## 1. Build

```bash
docker build -t probity .
```

## 2. See the failure mode

```bash
docker run --rm probity demo-once
docker run --rm probity demo
```

`demo-once` shows why a single green run is tempting. `demo` repeats the same
task and produces the falsifying verdict. The full demo returns `KILL` by
design; the Docker wrapper exits `0` for this demo command so a first-time user
does not mistake the expected KILL for a broken install.

## 3. Run the gates

```bash
docker run --rm probity calibrate
docker run --rm probity test
```

With Docker Compose:

```bash
docker compose run --rm demo-once
docker compose run --rm demo
docker compose run --rm calibrate
docker compose run --rm test
```

## 4. Run a task from your machine

Mount a folder that contains your `task_case.json` and any fixture files it
references:

```bash
docker run --rm -v "$PWD:/work" probity run /work/path/to/task_case.json
```

On PowerShell:

```powershell
docker run --rm -v "${PWD}:/work" probity run /work/path/to/task_case.json
```

`run` preserves Probity's real exit code:

- `0` when the suite verdict is PASS;
- `1` when the suite verdict is KILL or INSUFFICIENT;
- `2` for task rejection or spec drift.

That behavior is intentional for CI.

## 5. Bring your own agent CLI

Probity's subprocess adapter calls the agent command from inside the execution
environment. With Docker, that means the agent CLI must also exist inside the
container.

There are two practical options:

### Option A — use local Python when the agent CLI lives on your host

If your agent is installed on the host, run Probity on the host too:

```bash
python -m gauntlet run path/to/task_case.json
```

This lets `agent.behavior.cmd` call tools already installed on your machine.

### Option B — build a derived image

Create a small image that starts from Probity and installs your agent CLI:

```dockerfile
FROM probity

# Example only. Install your own CLI/toolchain here.
# RUN npm install -g your-agent-cli
# RUN python -m pip install your-agent-package
```

Then run:

```bash
docker build -t probity-with-my-agent -f Dockerfile.agent .
docker run --rm -v "$PWD:/work" probity-with-my-agent run /work/task_case.json
```

## 6. Minimal task shape

```json
{
  "task_id": "my_agent_audit_01",
  "suite": "local",
  "description": "Audit my agent on a deterministic task.",
  "workspace": {
    "type": "git",
    "path": "path/to/fixture_or_repo",
    "pristine_ref": "HEAD"
  },
  "agent_input": {
    "prompt": "Fix the task. Do not edit tests.",
    "env": {}
  },
  "checker": {
    "type": "pytest",
    "cmd": ["python", "-m", "pytest", "-q"],
    "allowed_paths": ["src/**"],
    "protected_paths": ["tests/**"],
    "critical_rules": []
  },
  "required_reliability": 0.90,
  "criticality": "standard",
  "k_planned": 10,
  "sampling": {"seed_policy": "incremental", "temperature": null},
  "agent": {
    "adapter": "subprocess",
    "agent_id": "my-agent",
    "behavior": {
      "cmd": ["my-agent", "--prompt-file", "{prompt_file}"],
      "timeout_s": 600
    }
  }
}
```

For full schema details, see `INTERFACE_CONTRACT.md`.

## Boundary

Docker is a convenience wrapper. It does not change Probity's core contract:
checker -> stats -> verdict remains deterministic and zero-LLM.
