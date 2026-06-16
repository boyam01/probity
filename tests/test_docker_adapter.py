"""A3 (D-040): opt-in docker sandbox adapter. Constructor validation + make_adapter routing are
testable everywhere; an actual container run is guarded on docker being installed. The core stays
zero-dependency: docker is imported only when adapter == "docker" is selected."""
import shutil
import subprocess

import pytest


def _docker_usable() -> bool:
    """docker is only usable if the CLI is on PATH AND the daemon answers (CLI present but daemon
    down is common on dev boxes; the integration run is skipped, not failed, in that case)."""
    if shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False

from probity.adapters.docker import DockerAgent
from probity.runner import make_adapter
from probity.types import (
    AgentInput,
    AgentSpec,
    CheckerSpec,
    SamplingSpec,
    TaskCase,
    WorkspaceSpec,
)


def _docker_task(behavior: dict) -> TaskCase:
    return TaskCase(
        task_id="d",
        suite="test",
        description="docker adapter",
        workspace=WorkspaceSpec(type="git", path="ws", pristine_ref="HEAD"),
        agent_input=AgentInput(prompt="do it"),
        checker=CheckerSpec(type="pytest", cmd=["python", "-m", "pytest", "-q"]),
        required_reliability=0.9,
        sampling=SamplingSpec(),
        agent=AgentSpec(adapter="docker", agent_id="d1", behavior=behavior),
    )


def test_docker_requires_image():
    with pytest.raises(ValueError):
        DockerAgent({"cmd": ["echo", "hi"]})


def test_docker_requires_cmd():
    with pytest.raises(ValueError):
        DockerAgent({"image": "alpine:3"})


def test_make_adapter_routes_docker():
    adapter = make_adapter(_docker_task({"image": "alpine:3", "cmd": ["echo", "hi"]}))
    assert type(adapter).__name__ == "DockerAgent"
    assert adapter.agent_id == "d1"


@pytest.mark.skipif(not _docker_usable(), reason="docker daemon not available")
def test_docker_run_executes(tmp_path):
    (tmp_path / "marker.txt").write_text("x", encoding="utf-8")
    adapter = DockerAgent({"image": "alpine:3", "cmd": ["sh", "-c", "echo CLAIM: success"]})
    task = _docker_task({"image": "alpine:3", "cmd": ["sh", "-c", "echo CLAIM: success"]})
    outcome = adapter.run(tmp_path, task, seed=1)
    assert "CLAIM: success" in outcome.trace.final_output
