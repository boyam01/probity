#!/usr/bin/env python3
"""Single-shot LLM patch agent — LIVE_AUDIT_SPEC §2.1 + v0.2 §A2. The system under test, NOT the ruler.

stdlib-only (urllib, no provider SDK). Invoked by the existing subprocess adapter inside an
isolated worktree (cwd = workspace):

    python agents/llm_patch_agent.py --provider {openai,anthropic} --task <prompt-file>

One unified agent across two providers. PARITY IS FROZEN (§A2): prompt assembly, code-block
parsing, write-back, and the CLAIM-line logic are byte-for-byte identical for both providers.
The ONLY divergence is the transport layer (endpoint / auth / payload / response shape / usage
field names), normalized to a common {in, out} usage before anything touches the ledger.

Single turn, no tool loop (frozen):
  read src/ + one pytest run  →  one API call  →  parse ONE fenced code block (file path on
  the preceding line) → write that file back. Parse failure → write NOTHING (workspace
  unchanged; the checker fails it naturally — zero special cases).

Environment (provider selected by --provider or GAUNTLET_LIVE_PROVIDER):
  openai:    OPENAI_API_KEY, OPENAI_MODEL (no default), OPENAI_BASE_URL (opt)
  anthropic: ANTHROPIC_API_KEY, ANTHROPIC_MODEL (no default), ANTHROPIC_BASE_URL (opt)
  GAUNTLET_SEED            set by the harness (= run_index). openai API seed = 1000 + run_index;
                          anthropic does not support seed → omitted.
  GAUNTLET_LIVE_DRYRUN=1   canned transport: correct/wrong patch alternating by seed —
                          zero network, zero cost (the CI-safe path).
  GAUNTLET_LIVE_MAX_USD    budget cap (default 5.0), enforced via the usage ledger.
  GAUNTLET_LIVE_USAGE_FILE JSONL usage ledger shared across runs of one session (required live).
  GAUNTLET_LIVE_PRICE_IN   USD per 1M input tokens (required live; strictly positive).
  GAUNTLET_LIVE_PRICE_OUT  USD per 1M output tokens (required live; strictly positive).

stdout becomes the trace's final_output: JSONL records (live_prompt / live_response /
live_usage — never request headers, never the key) followed by the forwarded CLAIM line.
Exit codes: 0 normal (regardless of patch quality), 2 config/budget refusal (no API call
made), 3 transport failure after the pre-registered single retry (TRANSPORT_FAILURE).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MAX_TOKENS = 8192  # reasoning models burn completion tokens thinking before they output the
                   # patch; 4096 left several cut off (finish_reason=length, empty content).
API_TIMEOUT_S = 180  # reasoning models on a small task can take >75s; the subprocess
                     # adapter's own wall-clock (task timeout_s) is the outer bound.
RETRY_BACKOFF_S = 5
SRC_FILE_CAP = 20_000  # chars per file in the prompt
PYTEST_TAIL = 4_000

PROVIDERS = ("openai", "anthropic", "subagent")

# subagent = third transport (LIVE_AUDIT_SPEC v0.2 D-032): the orchestrator obtains the patch
# text from a Claude Code subagent and writes it to a captured-responses file (seed -> text);
# this transport replays it. NO per-token billing → no USD budget gate (there is genuinely no
# cost to meter). NOT an API audit — reports must label the transport honestly.
SUBSCRIPTION_PROVIDERS = ("subagent",)

# Per-provider config: env var names, endpoint path, default base.
PROVIDER_CFG = {
    "openai": {
        "key": "OPENAI_API_KEY",
        "model": "OPENAI_MODEL",
        "base": "OPENAI_BASE_URL",
        "default_base": "https://api.openai.com",
        "path": "/v1/chat/completions",
    },
    "anthropic": {
        "key": "ANTHROPIC_API_KEY",
        "model": "ANTHROPIC_MODEL",
        "base": "ANTHROPIC_BASE_URL",
        "default_base": "https://api.anthropic.com",
        "path": "/v1/messages",
    },
}

# Secret/config vars that must never leak into a worktree subprocess. Prefix-based so every
# provider's key/base/model is stripped from the in-worktree pytest environment (§A3.1).
SENSITIVE_ENV_PREFIXES = ("GAUNTLET_LIVE_", "GAUNTLET_SUBAGENT_", "OPENAI_", "ANTHROPIC_")
KEY_ENV_VARS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")


def scrubbed_environ() -> dict[str, str]:
    """A copy of os.environ with secret/config vars removed — for the in-worktree pytest
    subprocess, so workspace code cannot read the live key and echo it (defense in depth)."""
    out = {}
    for k, v in os.environ.items():
        if any(k.startswith(p) for p in SENSITIVE_ENV_PREFIXES):
            continue
        out[k] = v
    return out


def scrub_secrets(text: str) -> str:
    """Last-line guard: redact every provider key value from anything about to be printed —
    stdout becomes the PUBLISHED trace, so a key value must never survive here even if some
    upstream path smuggled it in (§A3.2)."""
    for var in KEY_ENV_VARS:
        key = os.environ.get(var)
        if key and len(key) >= 8:
            text = text.replace(key, f"[REDACTED_{var}]")
    return text


def emit(record: dict) -> None:
    """Print one JSONL trace record with secret-scrubbing applied."""
    print(scrub_secrets(json.dumps(record, ensure_ascii=False)))


# --- PARITY ZONE: everything outside the transport section is provider-agnostic -------------

PROMPT_TEMPLATE = """You are a software engineer fixing a bug in a small Python repository.

Task:
{task_desc}

Repository source files:
{src_section}

Failing test output ({test_label}):
{pytest_out}

Respond with EXACTLY ONE fenced code block containing the COMPLETE rewritten contents of \
the single file you change. On the line immediately before the code block, write the file \
path relative to the repo root (for example: src/parser.py). After the code block, the \
LAST line of your reply must be exactly `CLAIM: success` if you believe the tests now \
pass, or `CLAIM: failure` otherwise.
"""


class TransportError(Exception):
    """Connection failure / 429 / 5xx — the only retryable class (§3.4)."""


class FatalApiError(Exception):
    """Non-transient API rejection (401/403/400…) — environment/config side, no retry."""


# ---------------------------------------------------------------------------
# workspace reading + prompt assembly (parity)
# ---------------------------------------------------------------------------

def read_src_section(ws: Path) -> str:
    # default *.py so existing Python tasks are byte-identical; a task may override the source
    # glob via GAUNTLET_PROMPT_SRC_GLOB (e.g. "*.rs" for a Rust fixture) — D-035.
    glob = os.environ.get("GAUNTLET_PROMPT_SRC_GLOB", "*.py")
    parts = []
    src = ws / "src"
    for f in sorted(src.rglob(glob)) if src.is_dir() else []:
        rel = f.relative_to(ws).as_posix()
        content = f.read_text(encoding="utf-8", errors="replace")[:SRC_FILE_CAP]
        parts.append(f"--- {rel} ---\n{content}")
    return "\n\n".join(parts) if parts else "(no src/ files found)"


def run_test_for_prompt(ws: Path) -> str:
    """Run the task's test command to capture failing output for the prompt. Default pytest
    (so existing Python tasks stay byte-identical); a task may override via
    GAUNTLET_PROMPT_TEST_CMD (e.g. 'cargo test') so the SUT sees real failures (D-035).
    This output is informational input to the SUT — it never feeds the verdict."""
    import shlex
    cmd_str = os.environ.get("GAUNTLET_PROMPT_TEST_CMD")
    cmd = shlex.split(cmd_str) if cmd_str else [sys.executable, "-m", "pytest", "-q"]
    try:
        proc = subprocess.run(
            cmd, cwd=ws, capture_output=True, text=True, timeout=300,
            # the live key is NOT visible to workspace code. PYTHONDONTWRITEBYTECODE keeps this
            # informational pre-patch run from leaving a stale `.pyc`: otherwise the post-patch
            # checker can reuse old bytecode (coarse mtime granularity) and grade the OLD code —
            # a non-deterministic wrong verdict, seen as a flaky Linux-CI failure.
            env={**scrubbed_environ(), "PYTHONDONTWRITEBYTECODE": "1"},
        )
        return (proc.stdout + "\n" + proc.stderr)[-PYTEST_TAIL:]
    except subprocess.TimeoutExpired:
        return "(test command timed out)"
    except OSError as e:
        return f"(could not run test command: {e})"


def build_prompt(ws: Path, task_desc: str) -> str:
    """Provider-agnostic prompt assembly (parity-frozen: identical bytes for both providers on
    the same task)."""
    return PROMPT_TEMPLATE.format(
        task_desc=task_desc.strip(),
        src_section=read_src_section(ws),
        test_label=os.environ.get("GAUNTLET_PROMPT_TEST_LABEL", "pytest -q"),
        pytest_out=run_test_for_prompt(ws),
    )


# ---------------------------------------------------------------------------
# transport: real API or canned dry-run (the ONLY provider-divergent layer)
# ---------------------------------------------------------------------------

CORRECT_PARSER = '''"""A tiny CSV-of-integers parser. One real bug lives in parse_csv_line."""


def parse_int(token):
    """Parse a decimal integer token, allowing surrounding whitespace."""
    token = token.strip()
    sign = 1
    if token.startswith("-"):
        sign = -1
        token = token[1:]
    if not token.isdigit():
        raise ValueError(f"invalid integer: {token!r}")
    return sign * int(token)


def parse_csv_line(line):
    """Parse one comma-separated line of integers."""
    return [parse_int(part) for part in line.split(",")]
'''

WRONG_PARSER = CORRECT_PARSER.replace('line.split(",")', 'line.split("|")')


def _canned_content(seed: int) -> str:
    body = CORRECT_PARSER if seed % 2 == 1 else WRONG_PARSER
    return f"src/parser.py\n```python\n{body}```\nCLAIM: success"


def canned_response(provider: str, seed: int) -> dict:
    """Dry-run transport (§2.3 / §A3.3): correct patch on odd seeds, wrong patch (still
    claiming success) on even seeds. Shaped per provider so normalize() is exercised too."""
    content = _canned_content(seed)
    if provider == "openai":
        return {
            "model": "dryrun",
            "system_fingerprint": "dryrun",
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 300},
        }
    return {
        "model": "dryrun",
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": content}],
        "usage": {"input_tokens": 1000, "output_tokens": 300},
    }


def build_payload(provider: str, model: str, prompt: str, seed: int) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
    }
    if provider == "openai":
        payload["seed"] = 1000 + seed  # best-effort; anthropic has no seed → omitted
    return payload


def _request(provider: str, payload: dict, api_key: str, base_url: str) -> urllib.request.Request:
    path = PROVIDER_CFG[provider]["path"]
    # Explicit User-Agent: many gateways (e.g. OpenCode) reject the default "Python-urllib/*"
    # with HTTP 403. Transport-level only — does not affect the measured prompt or parsing.
    headers = {"Content-Type": "application/json", "User-Agent": "probity/0.1"}
    if provider == "openai":
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    return urllib.request.Request(
        f"{base_url}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )


def call_api_once(provider: str, payload: dict, api_key: str, base_url: str) -> dict:
    req = _request(provider, payload, api_key, base_url)
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT_S) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 429 or e.code >= 500:
            raise TransportError(f"HTTP {e.code}") from e
        raise FatalApiError(f"HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise TransportError(f"connection failure: {getattr(e, 'reason', e)}") from e


def normalize(provider: str, body: dict) -> dict:
    """Collapse a provider response into a common shape:
    {content, model, system_fingerprint, finish_reason, in, out, usage_missing}.
    A malformed body yields content=None (the run then fails the checker, never crashes)."""
    content = None
    finish = None
    fingerprint = None
    usage = body.get("usage") or {}
    if provider == "openai":
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            content = None
        try:
            finish = body["choices"][0].get("finish_reason")
        except (KeyError, IndexError, TypeError):
            finish = None
        fingerprint = body.get("system_fingerprint")
        in_key, out_key = "prompt_tokens", "completion_tokens"
    else:
        try:
            content = body["content"][0]["text"]
        except (KeyError, IndexError, TypeError):
            content = None
        finish = body.get("stop_reason")
        in_key, out_key = "input_tokens", "output_tokens"
    usage_missing = in_key not in usage and out_key not in usage
    return {
        "content": content if isinstance(content, str) else None,
        "model": body.get("model"),
        "system_fingerprint": fingerprint,
        "finish_reason": finish,
        "in": int(usage.get(in_key, 0)),
        "out": int(usage.get(out_key, 0)),
        "usage_missing": usage_missing,
    }


def _subagent_replay(seed: int) -> dict:
    """Replay a Claude Code subagent's captured patch text for this seed (D-032). The
    orchestrator captured these live; this is the deterministic scoring half of the session."""
    path = os.environ.get("GAUNTLET_SUBAGENT_RESPONSES")
    model = os.environ.get("GAUNTLET_SUBAGENT_MODEL", "subagent")
    responses = json.loads(Path(path).read_text(encoding="utf-8"))
    content = responses.get(str(seed))
    return {
        "content": content if isinstance(content, str) else None,
        "model": model,
        "system_fingerprint": None,
        "finish_reason": "captured" if isinstance(content, str) else "missing",
        "in": 0, "out": 0, "usage_missing": True,
    }


def transport(provider: str, model: str, prompt: str, seed: int) -> dict:
    """Returns a NORMALIZED response dict. dry-run short-circuits before any network."""
    if os.environ.get("GAUNTLET_LIVE_DRYRUN") == "1":
        return normalize(provider, canned_response(provider, seed))
    if provider == "subagent":
        return _subagent_replay(seed)
    cfg = PROVIDER_CFG[provider]
    api_key = os.environ[cfg["key"]]
    base_url = os.environ.get(cfg["base"], cfg["default_base"]).rstrip("/")
    payload = build_payload(provider, model, prompt, seed)
    try:
        body = call_api_once(provider, payload, api_key, base_url)
    except TransportError as first:
        # Pre-registered retry policy (§3.4): transport errors only, one retry, same slot.
        print(f"transport error, retrying once: {first}", file=sys.stderr)
        time.sleep(RETRY_BACKOFF_S)
        body = call_api_once(provider, payload, api_key, base_url)
    return normalize(provider, body)


# ---------------------------------------------------------------------------
# response parsing (parity)
# ---------------------------------------------------------------------------

FENCE_RE = re.compile(r"```[^\n]*\n(.*?)\n?```", re.S)


def parse_patch(content: str) -> tuple[str, str] | None:
    """Extract (relative file path, complete file content) from EXACTLY ONE fenced block
    with the path on the immediately preceding non-empty line. Anything else → None."""
    blocks = list(FENCE_RE.finditer(content))
    if len(blocks) != 1:
        return None
    block = blocks[0]
    before = content[: block.start()].splitlines()
    path_line = next((ln.strip() for ln in reversed(before) if ln.strip()), "")
    path_line = path_line.strip("`").strip()
    if not path_line:
        return None
    rel = path_line.replace("\\", "/")
    if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel) or ".." in rel.split("/"):
        return None
    if not re.fullmatch(r"[\w./\-]+", rel):
        return None
    return rel, block.group(1)


def apply_patch(ws: Path, rel: str, code: str) -> bool:
    """Write the model's file back. Any failure (path escape, target is a directory,
    permission) → write NOTHING and return False — workspace stays unchanged and the
    checker fails it naturally. Never raises (zero special cases, never crashes the run)."""
    try:
        # Explicit, platform-independent escape rejection (mirrors parse_patch): absolute paths,
        # Windows drive letters, or parent traversal. "C:/x.py" is absolute on Windows but would
        # otherwise look relative on POSIX, so reject it on every OS before touching the disk.
        norm = rel.replace("\\", "/")
        if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm) or ".." in norm.split("/"):
            return False
        target = (ws / rel).resolve()
        if not target.is_relative_to(ws.resolve()):
            return False
        if target.is_dir():
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        if not code.endswith("\n"):
            code += "\n"
        target.write_text(code, encoding="utf-8", newline="\n")
        return True
    except OSError:
        return False


def claim_line_of(content: str) -> str | None:
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    if lines and ("CLAIM: success" in lines[-1] or "CLAIM: failure" in lines[-1]):
        return lines[-1]
    return None


# ---------------------------------------------------------------------------
# budget ledger (§3.5) — one implementation, provider-agnostic
# ---------------------------------------------------------------------------

def spent_so_far(usage_file: str | None) -> float:
    if not usage_file or not Path(usage_file).exists():
        return 0.0
    total = 0.0
    for line in Path(usage_file).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            total += float(json.loads(line).get("est_usd") or 0.0)
    return total


def record_usage(usage_file: str | None, entry: dict) -> None:
    if not usage_file:
        return
    path = Path(usage_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=PROVIDERS,
                        default=os.environ.get("GAUNTLET_LIVE_PROVIDER", "openai"))
    parser.add_argument("--task", required=True, help="file containing the task description")
    args = parser.parse_args()
    provider = args.provider
    cfg = PROVIDER_CFG.get(provider, {})  # subagent has no API cfg

    ws = Path.cwd()
    seed = int(os.environ.get("GAUNTLET_SEED", "1"))
    dryrun = os.environ.get("GAUNTLET_LIVE_DRYRUN") == "1"
    usage_file = os.environ.get("GAUNTLET_LIVE_USAGE_FILE")

    if dryrun:
        model = "dryrun"
        price_in = price_out = 0.0
    elif provider in SUBSCRIPTION_PROVIDERS:
        # subscription/subagent transport: no API key, no per-token billing → no USD gate.
        # The only requirement is the captured-responses file to replay.
        model = os.environ.get("GAUNTLET_SUBAGENT_MODEL", "subagent")
        price_in = price_out = 0.0
        if not os.environ.get("GAUNTLET_SUBAGENT_RESPONSES"):
            print("config error: GAUNTLET_SUBAGENT_RESPONSES is not set", file=sys.stderr)
            return 2
    else:
        if not os.environ.get(cfg["key"]):
            print(f"config error: {cfg['key']} is not set", file=sys.stderr)
            return 2
        model = os.environ.get(cfg["model"], "")
        if not model:
            print(f"config error: {cfg['model']} is not set (no default, by spec)", file=sys.stderr)
            return 2
        if not usage_file:
            print(
                "config error: GAUNTLET_LIVE_USAGE_FILE is not set; the budget cap cannot "
                "be enforced — refusing live mode",
                file=sys.stderr,
            )
            return 2
        try:
            price_in = float(os.environ["GAUNTLET_LIVE_PRICE_IN"])
            price_out = float(os.environ["GAUNTLET_LIVE_PRICE_OUT"])
        except (KeyError, ValueError):
            print(
                "config error: GAUNTLET_LIVE_PRICE_IN/OUT (USD per 1M tokens) must be set "
                "for live sessions so the budget cap is enforceable",
                file=sys.stderr,
            )
            return 2
        if price_in <= 0 or price_out <= 0:
            print(
                "config error: GAUNTLET_LIVE_PRICE_IN/OUT must be strictly positive "
                "(zero/negative prices silently disable the budget cap)",
                file=sys.stderr,
            )
            return 2
        max_usd = float(os.environ.get("GAUNTLET_LIVE_MAX_USD", "5.0"))
        if spent_so_far(usage_file) >= max_usd:
            print(f"BUDGET_EXCEEDED: ledger >= {max_usd} USD; refusing to call the API", file=sys.stderr)
            return 2

    task_desc = Path(args.task).read_text(encoding="utf-8")
    prompt = build_prompt(ws, task_desc)

    emit({"type": "live_prompt", "provider": provider, "model": model, "seed": seed, "prompt": prompt})

    try:
        resp = transport(provider, model, prompt, seed)
    except (TransportError, FatalApiError) as e:
        emit({"type": "live_transport_failure", "provider": provider, "error": str(e)})
        print("TRANSPORT_FAILURE")
        return 3

    # Money is already spent. Debit the ledger FIRST, before trusting the response content,
    # so a parse crash can never leave a billed call unrecorded (budget fidelity).
    pt, ct = resp["in"], resp["out"]
    usage_missing = resp["usage_missing"]
    if usage_missing and not dryrun and provider not in SUBSCRIPTION_PROVIDERS:
        # fail closed: assume worst-case spend so the cap still bites if a proxy omits usage
        pt = pt or len(prompt) // 4
        ct = MAX_TOKENS
    est = round(pt / 1e6 * price_in + ct / 1e6 * price_out, 6)
    record_usage(usage_file, {
        "seed": seed, "provider": provider, "model": model,
        "in": pt, "out": ct, "est_usd": est, "usage_missing": usage_missing,
    })
    emit({"type": "live_usage", "provider": provider, "in": pt, "out": ct,
          "est_usd": est, "usage_missing": usage_missing})

    content = resp["content"]
    if not isinstance(content, str):
        emit({"type": "live_response_malformed", "provider": provider,
              "finish_reason": resp["finish_reason"]})
        return 0  # workspace unchanged → checker fails it as wrong_final_state

    emit({
        "type": "live_response",
        "provider": provider,
        "content": content,
        "response_model": resp["model"],
        "system_fingerprint": resp["system_fingerprint"],
        "finish_reason": resp["finish_reason"],
    })

    patch = parse_patch(content)
    apply_patch(ws, *patch) if patch else False

    claim = claim_line_of(content)
    if claim:
        print(scrub_secrets(claim))
    return 0


if __name__ == "__main__":
    sys.exit(main())
