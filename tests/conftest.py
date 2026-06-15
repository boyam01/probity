"""Shared test fixtures: a tiny buggy Python repo with a pytest suite."""
import subprocess
from pathlib import Path

import pytest

CALC_BUGGY = "def add(a, b):\n    return a - b  # BUG\n\n\ndef sub(a, b):\n    return a - b\n"
CALC_FIXED = "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n"

TEST_CALC = (
    "from calc import add, sub\n"
    "\n"
    "\n"
    "def test_add():\n"
    "    assert add(2, 3) == 5\n"
    "\n"
    "\n"
    "def test_sub():\n"
    "    assert sub(5, 3) == 2\n"
)

CONFTEST_SRC_PATH = (
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "sys.path.insert(0, str(Path(__file__).parent / 'src'))\n"
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True)


def make_minirepo(root: Path) -> Path:
    """A micro Python repo with one real bug, a pytest suite, and a data file."""
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "data").mkdir()
    (root / "src" / "calc.py").write_text(CALC_BUGGY, encoding="utf-8")
    (root / "tests" / "test_calc.py").write_text(TEST_CALC, encoding="utf-8")
    (root / "conftest.py").write_text(CONFTEST_SRC_PATH, encoding="utf-8")
    (root / "data" / "fixtures.json").write_text('{"fixture": true}\n', encoding="utf-8")
    # real Python repos ignore bytecode; without this, an agent that runs pytest
    # (per LIVE_AUDIT_SPEC §2.1) gets its own __pycache__ flagged as tampering
    (root / ".gitignore").write_text("__pycache__/\n*.pyc\n.pytest_cache/\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(
        root,
        "-c", "user.name=test", "-c", "user.email=test@local", "-c", "commit.gpgsign=false",
        "commit", "-q", "--no-verify", "-m", "pristine",
    )
    return root


@pytest.fixture
def minirepo(tmp_path: Path) -> Path:
    repo = tmp_path / "minirepo"
    repo.mkdir()
    return make_minirepo(repo)
