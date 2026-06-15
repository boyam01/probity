"""LIVE_AUDIT_SPEC §2 tests: parsing, scrub, dry-run end-to-end (CI-safe, zero network)."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from gauntlet.runner import run_suite, run_task
from gauntlet.types import TaskCase
from gauntlet.verdict import decide

REPO_ROOT = Path(__file__).resolve().parent.parent
LIVE_TASK = REPO_ROOT / "tasks" / "live" / "task_live_openai.json"
LIVE_TASK_ANTHROPIC = REPO_ROOT / "tasks" / "live" / "task_live_anthropic.json"
AGENT_PATH = REPO_ROOT / "agents" / "llm_patch_agent.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


agent_mod = _load_module(AGENT_PATH, "llm_patch_agent")


# -- parse_patch ---------------------------------------------------------------

GOOD_RESPONSE = "Here is the fix.\n\nsrc/parser.py\n```python\nx = 1\n```\nCLAIM: success"


def test_parse_patch_standard_format():
    assert agent_mod.parse_patch(GOOD_RESPONSE) == ("src/parser.py", "x = 1")


def test_parse_patch_backticked_path_line():
    content = "`src/parser.py`\n```python\nx = 1\n```\nCLAIM: success"
    assert agent_mod.parse_patch(content) == ("src/parser.py", "x = 1")


def test_parse_patch_no_block_is_none():
    assert agent_mod.parse_patch("no code here\nCLAIM: success") is None


def test_parse_patch_two_blocks_is_none():
    content = "a.py\n```\nx\n```\nb.py\n```\ny\n```"
    assert agent_mod.parse_patch(content) is None


def test_parse_patch_missing_path_line_is_none():
    assert agent_mod.parse_patch("```python\nx = 1\n```") is None


@pytest.mark.parametrize("path", ["/etc/passwd", "C:/win.ini", "../escape.py", "src/../../up.py"])
def test_parse_patch_rejects_unsafe_paths(path):
    content = f"{path}\n```python\nx = 1\n```"
    assert agent_mod.parse_patch(content) is None


def test_apply_patch_refuses_outside_workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    assert agent_mod.apply_patch(ws, "ok.py", "x = 1") is True
    assert (ws / "ok.py").read_text(encoding="utf-8") == "x = 1\n"


# -- claim forwarding -----------------------------------------------------------

def test_claim_line_success_and_failure():
    assert agent_mod.claim_line_of("stuff\nCLAIM: success") == "CLAIM: success"
    assert agent_mod.claim_line_of("stuff\nCLAIM: failure") == "CLAIM: failure"
    assert agent_mod.claim_line_of("no claim at the end") is None
    assert agent_mod.claim_line_of("CLAIM: success\nthen more") is None


# -- canned transport (§2.3) -----------------------------------------------------

def test_canned_response_alternates_by_seed():
    odd = agent_mod.canned_response("openai", 1)["choices"][0]["message"]["content"]
    even = agent_mod.canned_response("openai", 2)["choices"][0]["message"]["content"]
    assert 'line.split(",")' in odd
    assert 'line.split("|")' in even
    assert odd.strip().endswith("CLAIM: success")
    assert even.strip().endswith("CLAIM: success")  # wrong patch still claims success


# -- usage ledger -----------------------------------------------------------------

def test_usage_ledger_round_trip(tmp_path):
    ledger = tmp_path / "usage.jsonl"
    assert agent_mod.spent_so_far(str(ledger)) == 0.0
    agent_mod.record_usage(str(ledger), {"est_usd": 0.5})
    agent_mod.record_usage(str(ledger), {"est_usd": 0.25})
    assert agent_mod.spent_so_far(str(ledger)) == pytest.approx(0.75)


# -- dry-run end-to-end (the CI safety net) ----------------------------------------

def _live_task(k: int) -> TaskCase:
    task = TaskCase.from_dict(json.loads(LIVE_TASK.read_text(encoding="utf-8")))
    task.k_planned = k  # in-memory only
    return task


def test_dryrun_end_to_end_pipeline(tmp_path, monkeypatch):
    """GAUNTLET_LIVE_DRYRUN=1: prompt build → canned transport → parse → write-back →
    checker → verdict, zero network, zero keys."""
    monkeypatch.setenv("GAUNTLET_LIVE_DRYRUN", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.chdir(REPO_ROOT)  # {repo_root} template resolves to the launch cwd

    task = _live_task(k=4)
    results = run_task(task, repo_root=REPO_ROOT, traces_root=tmp_path / "traces")

    # odd seeds get the correct canned patch, even seeds the wrong one
    assert [r.success for r in results] == [True, False, True, False]
    for r in results:
        assert r.modified_files == ["src/parser.py"]
    # the wrong-patch runs claimed success → false_claim derived
    assert results[1].integrity_flags.false_claim is True
    assert results[3].integrity_flags.false_claim is True
    assert results[1].failure_class == "wrong_final_state"
    # trace carries prompt/response/usage records and the forwarded claim
    trace_text = (tmp_path / "traces" / task.task_id / "run_01.jsonl").read_text(encoding="utf-8")
    assert "live_prompt" in trace_text
    assert "live_response" in trace_text
    assert "live_usage" in trace_text
    assert "CLAIM: success" in trace_text


def test_dryrun_traces_contain_no_secrets(tmp_path, monkeypatch):
    """Scrub guarantee: even with a key present in the environment, nothing key-like or
    header-like reaches the trace."""
    monkeypatch.setenv("GAUNTLET_LIVE_DRYRUN", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-FAKE-NEVER-LOGGED")
    monkeypatch.chdir(REPO_ROOT)

    task = _live_task(k=2)
    run_task(task, repo_root=REPO_ROOT, traces_root=tmp_path / "traces")

    for f in (tmp_path / "traces" / task.task_id).glob("*.jsonl"):
        text = f.read_text(encoding="utf-8")
        assert "sk-FAKE-NEVER-LOGGED" not in text
        assert "Authorization" not in text
        assert "Bearer" not in text


def test_dryrun_verdict_shape(tmp_path, monkeypatch):
    """Full k=10 dry-run: 5/10 (odd seeds) against r=0.90 → KILL [RELIABILITY_REFUTED]
    with FALSE_CLAIM_PATTERN — deterministic by construction."""
    monkeypatch.setenv("GAUNTLET_LIVE_DRYRUN", "1")
    monkeypatch.chdir(REPO_ROOT)

    task = _live_task(k=10)
    data = run_suite([task], repo_root=REPO_ROOT, traces_root=tmp_path / "traces")
    audit = decide(task, data.results[task.task_id], data.env)

    assert audit.successes == 5
    assert audit.verdict == "KILL"
    assert audit.reason_codes == ["RELIABILITY_REFUTED"]  # hi(5/10)=0.7634 < 0.90
    assert "FALSE_CLAIM_PATTERN" in audit.diagnostics
    assert audit.integrity_summary.false_claim == 5


# -- live-agent config refusals ------------------------------------------------------

def test_agent_refuses_without_model_env(tmp_path, monkeypatch):
    """No OPENAI_MODEL default, by spec: the agent exits 2 before any API call."""
    monkeypatch.delenv("GAUNTLET_LIVE_DRYRUN", raising=False)
    env = {k: v for k, v in __import__("os").environ.items()
           if k not in ("OPENAI_MODEL", "GAUNTLET_LIVE_DRYRUN")}
    env["OPENAI_API_KEY"] = "sk-FAKE"
    prompt_file = tmp_path / "p.txt"
    prompt_file.write_text("fix it", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(AGENT_PATH), "--provider", "openai", "--task", str(prompt_file)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 2
    assert "OPENAI_MODEL" in proc.stderr


# -- session driver pre-registration gate ----------------------------------------------

def test_driver_refuses_without_committed_manifest(tmp_path):
    """§3.1: no committed SESSION_MANIFEST.md → the driver refuses before running anything."""
    out_rel = "reports/live/0000-00-00-unregistered-test"
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_live_session.py"),
         "--task", "tasks/live/task_live_openai.json", "--out", out_rel],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
        env={**__import__("os").environ, "GAUNTLET_LIVE_DRYRUN": "1"},
    )
    assert proc.returncode == 3
    assert "SESSION_MANIFEST" in proc.stderr


# -- security hardening (adversarial-review findings) ----------------------------------

def test_scrubbed_environ_drops_secrets(monkeypatch):
    """The in-worktree pytest must not inherit the live key (secret-channel finding)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-SECRET")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example")
    monkeypatch.setenv("GAUNTLET_LIVE_PRICE_IN", "1.0")
    monkeypatch.setenv("PATH_KEEPME", "ok")
    env = agent_mod.scrubbed_environ()
    assert "OPENAI_API_KEY" not in env
    assert "OPENAI_BASE_URL" not in env
    assert "GAUNTLET_LIVE_PRICE_IN" not in env
    assert env.get("PATH_KEEPME") == "ok"


def test_scrub_secrets_redacts_key_value(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-abcdef123456")
    assert "sk-abcdef123456" not in agent_mod.scrub_secrets("leak: sk-abcdef123456 here")
    assert "[REDACTED_OPENAI_API_KEY]" in agent_mod.scrub_secrets("sk-abcdef123456")


def test_apply_patch_never_crashes_on_directory_target(tmp_path):
    """A response path of 'src' (an existing dir) must NOT raise — write nothing, return False."""
    ws = tmp_path / "ws"
    (ws / "src").mkdir(parents=True)
    assert agent_mod.apply_patch(ws, "src", "x = 1") is False


@pytest.mark.parametrize("path", ["/abs.py", "C:/x.py", "../up.py"])
def test_apply_patch_rejects_escapes_without_raising(tmp_path, path):
    ws = tmp_path / "ws"
    ws.mkdir()
    # parse_patch already rejects these, but apply_patch must also be crash-safe directly
    assert agent_mod.apply_patch(ws, path, "x = 1") is False


def _live_env_base():
    import os as _os
    env = {k: v for k, v in _os.environ.items() if not k.startswith("GAUNTLET_LIVE")}
    env.pop("GAUNTLET_LIVE_DRYRUN", None)
    env["OPENAI_API_KEY"] = "sk-FAKE"
    env["OPENAI_MODEL"] = "gpt-test"
    return env


def _run_agent(env, tmp_path, provider="openai"):
    pf = tmp_path / "p.txt"
    pf.write_text("fix it", encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(AGENT_PATH), "--provider", provider, "--task", str(pf)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120,
    )


def test_agent_refuses_live_without_usage_ledger(tmp_path):
    """No GAUNTLET_LIVE_USAGE_FILE → the budget cap is unenforceable → refuse (exit 2)."""
    env = _live_env_base()
    env["GAUNTLET_LIVE_PRICE_IN"] = "1.0"
    env["GAUNTLET_LIVE_PRICE_OUT"] = "2.0"
    # deliberately no GAUNTLET_LIVE_USAGE_FILE
    proc = _run_agent(env, tmp_path)
    assert proc.returncode == 2
    assert "GAUNTLET_LIVE_USAGE_FILE" in proc.stderr


def test_agent_refuses_nonpositive_prices(tmp_path):
    env = _live_env_base()
    env["GAUNTLET_LIVE_USAGE_FILE"] = str(tmp_path / "u.jsonl")
    env["GAUNTLET_LIVE_PRICE_IN"] = "0"
    env["GAUNTLET_LIVE_PRICE_OUT"] = "0"
    proc = _run_agent(env, tmp_path)
    assert proc.returncode == 2
    assert "positive" in proc.stderr.lower()


def test_driver_secret_regex_catches_nonsk_and_skant_formats():
    drv = _load_module(REPO_ROOT / "scripts" / "run_live_session.py", "run_live_session")
    assert drv.SECRET_RE.search("sk-ant-api03-AAAA")  # anthropic key shape (§A3.2)
    assert drv.SECRET_RE.search("deadbeefdeadbeefdeadbeefdeadbeef")  # azure 32-hex
    assert drv.SECRET_RE.search("Bearer abcdefghijklmnop1234")
    assert drv.SECRET_RE.search("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")  # jwt
    assert drv.SECRET_RE.search("Authorization: x")
    assert drv.SECRET_RE.search("x-api-key: y")
    assert not drv.SECRET_RE.search("just a normal sentence about parsers")


def test_driver_publish_emits_artifacts_with_A4_publication_block(tmp_path, monkeypatch):
    """The publish path (§5 + §A4): audit_report.json + GAUNTLET_REPORT.md with the live
    header — stochastic disclaimer + 'single-turn patch agent built on' wording + the
    not-a-model-comparison clause — prepended + scrubbed traces. Dry-run, zero network."""
    monkeypatch.setenv("GAUNTLET_LIVE_DRYRUN", "1")
    monkeypatch.chdir(REPO_ROOT)
    drv = _load_module(REPO_ROOT / "scripts" / "run_live_session.py", "run_live_session3")

    from gauntlet import HARNESS_VERSION as HV
    from gauntlet.verdict import build_audit_report, decide

    task = _live_task(k=10)
    data = run_suite([task], repo_root=REPO_ROOT, traces_root=REPO_ROOT / "traces")
    runs = data.results[task.task_id]
    audit = decide(task, runs, data.env)
    report = build_audit_report([audit], data.env, "sha256:" + "a" * 64, HV)

    out = tmp_path / "2026-01-01-dryrun"
    md = drv.publish_session(out, report, task, runs, "tasks/live/task_live_openai.json",
                             provider="openai", model="gpt-x")

    assert (out / "audit_report.json").exists()
    assert (out / "GAUNTLET_REPORT.md").exists()
    assert md.startswith("> **Live audit disclaimer.**")
    assert "not bit-reproducible" in md
    # §A4.5 frozen wording + §A4.3 verbatim clause
    assert "a single-turn patch agent built on `gpt-x`" in md
    assert "It is not a model comparison" in md
    assert "deliberately refuses to produce one" in md
    # §A4.5: never the forbidden phrasing
    assert "we audited GPT" not in md and "we audited Claude" not in md
    traces = list((out / "traces").glob("*.jsonl"))
    assert len(traces) == 10
    for t in traces:
        text = t.read_text(encoding="utf-8")
        assert not drv.SECRET_RE.search(text), f"secret-like content in {t.name}"


def test_driver_manifest_must_bind_task_hash(tmp_path):
    """A committed manifest that doesn't record the task's sha256 → refuse (§3.1 binding)."""
    drv = _load_module(REPO_ROOT / "scripts" / "run_live_session.py", "run_live_session2")
    out = tmp_path / "session"
    out.mkdir()
    (out / "SESSION_MANIFEST.md").write_text("no hash here\n", encoding="utf-8")
    task = LIVE_TASK
    assert drv.manifest_binds_task(out, task) is False
    correct = drv._norm_hash(task)
    (out / "SESSION_MANIFEST.md").write_text(f"task sha256: {correct}\n", encoding="utf-8")
    assert drv.manifest_binds_task(out, task) is True


def test_driver_derives_provider_and_agent_from_task():
    drv = _load_module(REPO_ROOT / "scripts" / "run_live_session.py", "run_live_session4")
    t_oai = TaskCase.from_dict(json.loads(LIVE_TASK.read_text(encoding="utf-8")))
    t_ant = TaskCase.from_dict(json.loads(LIVE_TASK_ANTHROPIC.read_text(encoding="utf-8")))
    assert drv.task_provider_and_agent(t_oai) == ("openai", "agents/llm_patch_agent.py")
    assert drv.task_provider_and_agent(t_ant) == ("anthropic", "agents/llm_patch_agent.py")


# -- v0.2 §A2 PARITY: the two providers diverge ONLY at the transport layer ----------------

def test_parity_prompt_assembly_is_provider_agnostic(tmp_path, monkeypatch):
    """§A8.1: prompt assembly is identical bytes regardless of provider (it has no provider
    input at all — build_prompt depends only on workspace + task text)."""
    monkeypatch.chdir(REPO_ROOT)
    ws = REPO_ROOT / "demo" / "patchbot" / "minirepo"
    p1 = agent_mod.build_prompt(ws, "fix it")
    p2 = agent_mod.build_prompt(ws, "fix it")
    assert p1 == p2
    assert "Repository source files:" in p1


def test_parity_canned_content_identical_across_providers():
    """The dry-run patch body is the same for both providers; only the response envelope
    (openai choices/message vs anthropic content/text) differs — and normalize() collapses
    them to the same content."""
    for seed in (1, 2, 3, 4):
        oai = agent_mod.normalize("openai", agent_mod.canned_response("openai", seed))
        ant = agent_mod.normalize("anthropic", agent_mod.canned_response("anthropic", seed))
        assert oai["content"] == ant["content"]
        # parse/apply parity: identical patch extracted
        assert agent_mod.parse_patch(oai["content"]) == agent_mod.parse_patch(ant["content"])


def test_normalize_usage_field_mapping():
    """§A8.4: openai prompt_tokens/completion_tokens and anthropic input_tokens/output_tokens
    both normalize to {in, out}."""
    oai = agent_mod.normalize("openai", {
        "choices": [{"message": {"content": "x"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 22},
    })
    ant = agent_mod.normalize("anthropic", {
        "content": [{"type": "text", "text": "x"}], "stop_reason": "end_turn",
        "usage": {"input_tokens": 11, "output_tokens": 22},
    })
    assert (oai["in"], oai["out"]) == (11, 22)
    assert (ant["in"], ant["out"]) == (11, 22)
    assert oai["usage_missing"] is False and ant["usage_missing"] is False


def test_normalize_malformed_body_yields_none_content():
    assert agent_mod.normalize("openai", {"choices": []})["content"] is None
    assert agent_mod.normalize("anthropic", {"content": []})["content"] is None
    assert agent_mod.normalize("anthropic", {})["content"] is None
    # content=null (content_filter/refusal) → None, usage_missing True
    n = agent_mod.normalize("openai", {"choices": [{"message": {"content": None}}]})
    assert n["content"] is None and n["usage_missing"] is True


def test_build_payload_seed_only_for_openai():
    """§A2: openai sends seed=1000+run_index; anthropic omits seed entirely."""
    oai = agent_mod.build_payload("openai", "m", "prompt", 3)
    ant = agent_mod.build_payload("anthropic", "m", "prompt", 3)
    assert oai["seed"] == 1003
    assert "seed" not in ant
    # max_tokens present for both (anthropic requires it; openai parity)
    assert oai["max_tokens"] == ant["max_tokens"] == agent_mod.MAX_TOKENS
    # neither sends temperature
    assert "temperature" not in oai and "temperature" not in ant


def test_request_headers_per_provider():
    """Auth header diverges: openai Bearer, anthropic x-api-key + anthropic-version."""
    oai = agent_mod._request("openai", {}, "sk-KEY", "https://api.openai.com")
    ant = agent_mod._request("anthropic", {}, "sk-ant-KEY", "https://api.anthropic.com")
    assert oai.headers["Authorization"] == "Bearer sk-KEY"
    assert oai.full_url.endswith("/v1/chat/completions")
    # urllib title-cases header keys
    assert ant.headers["X-api-key"] == "sk-ant-KEY"
    assert ant.headers["Anthropic-version"] == "2023-06-01"
    assert "Authorization" not in ant.headers
    assert ant.full_url.endswith("/v1/messages")


def test_scrubbed_environ_drops_anthropic_too(monkeypatch):
    """§A3.1: ANTHROPIC_* also stripped from the in-worktree pytest env."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-SECRET")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-x")
    monkeypatch.setenv("KEEP_ME", "ok")
    env = agent_mod.scrubbed_environ()
    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_MODEL" not in env
    assert env.get("KEEP_ME") == "ok"


def test_scrub_secrets_redacts_skant_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-abc123456789")
    out = agent_mod.scrub_secrets("oops sk-ant-abc123456789 leaked")
    assert "sk-ant-abc123456789" not in out
    assert "[REDACTED_ANTHROPIC_API_KEY]" in out


def test_anthropic_dryrun_end_to_end(tmp_path, monkeypatch):
    """§A8.2: full anthropic dry-run through the harness — zero network, same verdict shape
    as openai (parity), driven by the --provider anthropic task."""
    monkeypatch.setenv("GAUNTLET_LIVE_DRYRUN", "1")
    monkeypatch.chdir(REPO_ROOT)
    task = TaskCase.from_dict(json.loads(LIVE_TASK_ANTHROPIC.read_text(encoding="utf-8")))
    task.k_planned = 4
    results = run_task(task, repo_root=REPO_ROOT, traces_root=tmp_path / "traces")
    assert [r.success for r in results] == [True, False, True, False]
    # parse the trace properly: the agent's stdout JSONL is JSON-escaped inside the trace
    from gauntlet.types import Trace
    trace = Trace.from_jsonl((tmp_path / "traces" / task.task_id / "run_01.jsonl").read_text(encoding="utf-8"))
    records = [json.loads(ln) for ln in trace.final_output.splitlines() if ln.strip().startswith("{")]
    types = {r.get("type"): r for r in records}
    assert types["live_prompt"]["provider"] == "anthropic"
    assert "live_usage" in types


def test_anthropic_dryrun_traces_have_no_secrets(tmp_path, monkeypatch):
    """§A3.4 spirit (automated dry-run version): a fake sk-ant key in env never reaches traces."""
    monkeypatch.setenv("GAUNTLET_LIVE_DRYRUN", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "xxx-anthropic-canary-never-logged-xxx")
    monkeypatch.chdir(REPO_ROOT)
    task = TaskCase.from_dict(json.loads(LIVE_TASK_ANTHROPIC.read_text(encoding="utf-8")))
    task.k_planned = 2
    run_task(task, repo_root=REPO_ROOT, traces_root=tmp_path / "traces")
    for f in (tmp_path / "traces" / task.task_id).glob("*.jsonl"):
        text = f.read_text(encoding="utf-8")
        assert "xxx-anthropic-canary-never-logged-xxx" not in text
        assert "x-api-key" not in text.lower()
