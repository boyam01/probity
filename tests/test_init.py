"""`probity init` scaffolds a schema-valid task_case.json template (zero-LLM)."""
import json

from probity.cli import main
from probity.types import TaskCase


def test_init_writes_valid_roundtrip_template(tmp_path):
    out = tmp_path / "task_case.json"
    rc = main(["init", str(out)])
    assert rc == 0
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    # must be a schema-valid TaskCase that round-trips byte-stably through the dataclasses
    tc = TaskCase.from_json(text)
    assert json.loads(tc.to_json()) == json.loads(text)
    # template targets the real-agent path and keeps the oracle protected
    assert tc.agent is not None and tc.agent.adapter == "subprocess"
    assert tc.checker.type in ("pytest", "script", "state_file")
    assert tc.checker.protected_paths


def test_init_refuses_overwrite_without_force(tmp_path):
    out = tmp_path / "task_case.json"
    out.write_text("{}", encoding="utf-8")
    rc = main(["init", str(out)])
    assert rc != 0
    assert out.read_text(encoding="utf-8") == "{}"  # left untouched


def test_init_force_overwrites(tmp_path):
    out = tmp_path / "task_case.json"
    out.write_text("{}", encoding="utf-8")
    rc = main(["init", str(out), "--force"])
    assert rc == 0
    assert TaskCase.from_json(out.read_text(encoding="utf-8")).task_id
