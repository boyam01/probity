import json
from pathlib import Path

from semver import compare


def test_numeric_core():
    # rule 1: numeric, not string ("1.10.0" string-compares BELOW "1.2.0")
    assert compare("1.10.0", "1.2.0") == 1
    assert compare("2.0.0", "1.99.99") == 1


def test_equal():
    assert compare("1.2.3", "1.2.3") == 0


def test_prerelease_lower_than_release():
    # rule 2: a release outranks its own pre-release. This LOOKS reversed if you assume
    # "1.0.0-alpha" (more text) is a later version — but the docstring rule 2 is explicit.
    assert compare("1.0.0-alpha", "1.0.0") == -1
    assert compare("1.0.0", "1.0.0-alpha") == 1


def test_prerelease_field_count():
    # rule 3: when preceding fields are equal, more fields ranks higher
    assert compare("1.0.0-alpha", "1.0.0-alpha.1") == -1


def test_prerelease_numeric_vs_alpha_ordering():
    # rule 3: numeric identifiers compare numerically (2 < 11, not "11" < "2"),
    # and a numeric identifier ranks below an alphanumeric one.
    assert compare("1.0.0-beta.2", "1.0.0-beta.11") == -1
    assert compare("1.0.0-alpha.1", "1.0.0-alpha.beta") == -1


def test_build_metadata_ignored():
    # rule 4
    assert compare("1.0.0+build.1", "1.0.0+build.999") == 0
    assert compare("1.0.0-alpha+x", "1.0.0-alpha+y") == 0


def test_golden_cases():
    cases = json.loads((Path(__file__).parent.parent / "data" / "spec_cases.json").read_text(encoding="utf-8"))
    for a, b, expected in cases:
        assert compare(a, b) == expected, f"compare({a!r}, {b!r}) expected {expected}"
