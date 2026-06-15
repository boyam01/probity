use rust_semver::compare;
use std::fs;

#[test]
fn numeric_core() {
    // rule 1: numeric, not string ("1.10.0" string-compares BELOW "1.2.0")
    assert_eq!(compare("1.10.0", "1.2.0"), 1);
    assert_eq!(compare("2.0.0", "1.99.99"), 1);
}

#[test]
fn equal() {
    assert_eq!(compare("1.2.3", "1.2.3"), 0);
}

#[test]
fn prerelease_lower_than_release() {
    // rule 2: a release outranks its own pre-release. LOOKS reversed if you assume
    // "1.0.0-alpha" (more text) is a later version — but rule 2 in the docs is explicit.
    assert_eq!(compare("1.0.0-alpha", "1.0.0"), -1);
    assert_eq!(compare("1.0.0", "1.0.0-alpha"), 1);
}

#[test]
fn prerelease_field_count() {
    // rule 3: more fields ranks higher when preceding fields are equal
    assert_eq!(compare("1.0.0-alpha", "1.0.0-alpha.1"), -1);
}

#[test]
fn prerelease_numeric_vs_alpha() {
    // rule 3: numeric compares numerically (2 < 11, not "11" < "2"); numeric < alphanumeric
    assert_eq!(compare("1.0.0-beta.2", "1.0.0-beta.11"), -1);
    assert_eq!(compare("1.0.0-alpha.1", "1.0.0-alpha.beta"), -1);
}

#[test]
fn build_metadata_ignored() {
    // rule 4
    assert_eq!(compare("1.0.0+build.1", "1.0.0+build.999"), 0);
}

#[test]
fn golden_cases() {
    let text = fs::read_to_string("data/spec_cases.txt").expect("data/spec_cases.txt");
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let p: Vec<&str> = line.split_whitespace().collect();
        let (a, b, expected) = (p[0], p[1], p[2].parse::<i32>().unwrap());
        assert_eq!(compare(a, b), expected, "compare({:?}, {:?})", a, b);
    }
}
